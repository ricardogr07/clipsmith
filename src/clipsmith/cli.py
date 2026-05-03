"""clipsmith CLI: `process`, `setup`, `watch`, `run-vod`, `clip`, `whoami`."""

from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path

import typer
from rich.console import Console

from .candidates import CandidateMoment
from .clipper import _cut_one, _find_ffmpeg, _title_slug, cut_all_clips
from .llm.base import ClipPick
from .pipeline import _process_vod, _setup_logging
from .selector import PickResult
from .settings import load_config, load_secrets
from .state import State
from .transcribe import Transcript
from .twitch_client import TwitchClient, Video
from .watcher import watch as watch_iter

app = typer.Typer(add_completion=False, help="Twitch -> AI clip pipeline")
console = Console()
log = logging.getLogger(__name__)


def _resolve_config(explicit: Path) -> Path:
    """Return config path: explicit arg > bundled next to exe > cwd default."""
    if explicit != Path("config.yaml"):
        return explicit
    bundled = Path(sys.executable).parent / "config.yaml"
    if bundled.exists():
        return bundled
    return explicit


@app.command()
def process(
    mp4: Path = typer.Argument(..., help="Path to a local MP4 file to process"),
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    provider: str | None = typer.Option(None, "--provider", help="Override LLM provider (anthropic|openai)"),
    captions: bool | None = typer.Option(None, "--captions/--no-captions", help="Burn captions into video (overrides config)"),
    reframe: bool | None = typer.Option(None, "--reframe/--no-reframe", help="Reframe to 9:16 vertical (overrides config)"),
    skip_transcribe: bool = typer.Option(False, "--skip-transcribe", help="Use cached transcript.json if it exists"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Process a local MP4 through the full pipeline: transcribe -> LLM -> clips."""
    _setup_logging(verbose)

    if not mp4.exists():
        console.print(f"[red]File not found:[/red] {mp4}")
        raise typer.Exit(1)
    if mp4.suffix.lower() != ".mp4":
        console.print(f"[red]Expected an .mp4 file, got:[/red] {mp4.suffix}")
        raise typer.Exit(1)

    cfg = load_config(_resolve_config(config_path))
    if captions is not None:
        cfg.caption.enabled = captions
    if reframe is not None:
        if not reframe:
            cfg.reframe.mode = "none"
        elif cfg.reframe.mode == "none":
            cfg.reframe.mode = "center"
    secrets = load_secrets()

    video_id = mp4.stem
    work_dir = cfg.work_dir.expanduser()
    dest = work_dir / video_id / f"{video_id}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if not dest.exists():
        console.print(f"[cyan]copying[/cyan] {mp4.name} -> {dest}")
        shutil.copy2(mp4, dest)
    else:
        console.print(f"[dim]using existing[/dim] {dest}")

    video = Video(
        id=video_id,
        user_id="",
        user_login=cfg.channels[0] if cfg.channels else "local",
        title=video_id,
        created_at="",
        published_at="",
        url="",
        duration="",
        type="archive",
    )

    try:
        _process_vod(
            video, cfg, secrets,
            skip_download=True,
            skip_transcribe=skip_transcribe,
            skip_chat=True,
            provider=provider,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)


@app.command()
def setup(
    provider: str | None = typer.Option(None, "--provider", help="LLM provider: anthropic or openai"),
    key: str | None = typer.Option(None, "--key", help="API key (omit to be prompted interactively)"),
) -> None:
    """First-run wizard: save your API key and verify ffmpeg is available."""
    env_path = Path(sys.executable).parent / ".env"

    if provider is None:
        provider = typer.prompt(
            "LLM provider",
            default="anthropic",
            prompt_suffix=" (anthropic/openai): ",
        ).strip().lower()

    if provider not in ("anthropic", "openai"):
        console.print(f"[red]Unknown provider:[/red] {provider}. Choose 'anthropic' or 'openai'.")
        raise typer.Exit(1)

    if key is None:
        key = typer.prompt(f"Paste your {provider} API key", hide_input=True).strip()

    if not key:
        console.print("[red]No key provided. Aborting.[/red]")
        raise typer.Exit(1)

    env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"

    # Read existing .env lines, replacing or appending the key.
    existing: list[str] = []
    if env_path.exists():
        existing = env_path.read_text(encoding="utf-8").splitlines()

    updated = [ln for ln in existing if not ln.startswith(f"{env_var}=")]
    updated.append(f"{env_var}={key}")
    env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
    console.print(f"[green]Saved[/green] {env_var} to {env_path}")

    # Verify ffmpeg.
    ffmpeg = _find_ffmpeg()
    if Path(ffmpeg).exists() or shutil.which(ffmpeg):
        console.print(f"[green]ffmpeg found[/green]: {ffmpeg}")
    else:
        console.print(
            "[yellow]ffmpeg not found.[/yellow] "
            "Place ffmpeg.exe in the same folder as clipsmith.exe."
        )

    console.print("\n[bold]Ready.[/bold] Run: clipsmith process path\\to\\video.mp4")


@app.command()
def watch(
    channel: str | None = typer.Argument(None, help="Override config channel(s)"),
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    once: bool = typer.Option(False, "--once", help="Single poll pass, then exit"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Poll Twitch for new archive VODs and run the full pipeline for each."""
    _setup_logging(verbose)
    cfg = load_config(config_path)
    if channel:
        cfg.channels = [channel]
    if not cfg.channels:
        console.print("[red]No channels configured.[/red] Add to config.yaml or pass one as arg.")
        raise typer.Exit(2)
    secrets = load_secrets()
    state = State()
    console.print(f"watching: {', '.join(cfg.channels)} (poll={cfg.poll_interval_s}s)")
    for event in watch_iter(cfg, secrets, state=state, once=once):
        console.print(
            f"[green]new VOD[/green]: {event.video.id}  {event.video.title!r}  ({event.video.duration})"
        )
        try:
            _process_vod(event.video, cfg, secrets)
        except Exception as exc:
            log.exception("pipeline failed for VOD %s", event.video.id)
            console.print(f"[red]error — VOD {event.video.id} skipped:[/red] {exc}")


@app.command("run-vod")
def run_vod(
    video_id: str = typer.Argument(..., help="Twitch video (VOD) id"),
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    local: bool = typer.Option(False, "--local", help="Skip all Twitch API calls; use manually placed mp4"),
    skip_download: bool = typer.Option(False, "--skip-download", help="Use existing mp4 in work dir"),
    skip_transcribe: bool = typer.Option(False, "--skip-transcribe", help="Use cached transcript.json"),
    skip_chat: bool = typer.Option(False, "--skip-chat", help="Use cached chat.json"),
    skip_select: bool = typer.Option(False, "--skip-select", help="Skip LLM selection step"),
    skip_clip: bool = typer.Option(False, "--skip-clip", help="Skip ffmpeg clipping step"),
    provider: str | None = typer.Option(None, "--provider", help="Override LLM provider (anthropic|openai)"),
    captions: bool | None = typer.Option(None, "--captions/--no-captions", help="Burn captions into video (overrides config)"),
    reframe: bool | None = typer.Option(None, "--reframe/--no-reframe", help="Reframe to 9:16 vertical (overrides config)"),
    max_candidates: int = typer.Option(20, "--max-candidates", help="Max candidates to send to LLM"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Download, transcribe, score candidates, and select clips via LLM."""
    _setup_logging(verbose)
    cfg = load_config(config_path)
    if captions is not None:
        cfg.caption.enabled = captions
    if reframe is not None:
        if not reframe:
            cfg.reframe.mode = "none"
        elif cfg.reframe.mode == "none":
            cfg.reframe.mode = "center"
    secrets = load_secrets()

    if local:
        video = Video(
            id=video_id,
            user_id="",
            user_login=cfg.channels[0] if cfg.channels else "local",
            title=video_id,
            created_at="",
            published_at="",
            url=f"https://www.twitch.tv/videos/{video_id}",
            duration="",
            type="archive",
        )
        skip_download = True
    else:
        with TwitchClient(secrets.twitch_client_id, secrets.twitch_client_secret) as tc:
            body = tc._get("/videos", {"id": video_id})  # noqa: SLF001
            data = body.get("data") or []
            if not data:
                console.print(f"[red]VOD not found:[/red] {video_id}")
                raise typer.Exit(1)
            v = data[0]

        video = Video(
            id=v["id"],
            user_id=v["user_id"],
            user_login=v["user_login"],
            title=v["title"],
            created_at=v["created_at"],
            published_at=v.get("published_at", v["created_at"]),
            url=v["url"],
            duration=v["duration"],
            type=v["type"],
        )

    try:
        _process_vod(
            video, cfg, secrets,
            skip_download=skip_download,
            skip_transcribe=skip_transcribe,
            skip_chat=skip_chat,
            skip_select=skip_select,
            skip_clip=skip_clip,
            provider=provider,
            max_candidates=max_candidates,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)


@app.command("clip")
def clip_cmd(
    video_id: str = typer.Argument(..., help="Twitch video (VOD) id"),
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    captions: bool | None = typer.Option(None, "--captions/--no-captions", help="Burn captions into video (overrides config)"),
    reframe: bool | None = typer.Option(None, "--reframe/--no-reframe", help="Reframe to 9:16 vertical (overrides config)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Re-run the ffmpeg clipper from an existing picks.json (no LLM re-call)."""
    _setup_logging(verbose)
    cfg = load_config(config_path)
    if captions is not None:
        cfg.caption.enabled = captions
    if reframe is not None:
        if not reframe:
            cfg.reframe.mode = "none"
        elif cfg.reframe.mode == "none":
            cfg.reframe.mode = "center"

    work_dir = cfg.work_dir.expanduser()
    vod_dir = work_dir / video_id

    picks_path = vod_dir / "picks.json"
    if not picks_path.exists():
        console.print(f"[red]picks.json not found:[/red] {picks_path}")
        raise typer.Exit(1)

    raw = json.loads(picks_path.read_text(encoding="utf-8"))
    picks = [
        PickResult(
            candidate=CandidateMoment(**p["candidate"]),
            pick=ClipPick.from_dict(p["pick"]),
        )
        for p in raw
    ]

    transcript_path = vod_dir / "transcript.json"
    if not transcript_path.exists():
        console.print(f"[red]transcript.json not found:[/red] {transcript_path}")
        raise typer.Exit(1)
    transcript = Transcript.from_json(transcript_path.read_text(encoding="utf-8"))

    mp4_path = vod_dir / f"{video_id}.mp4"
    if not mp4_path.exists():
        console.print(f"[red]MP4 not found:[/red] {mp4_path}")
        raise typer.Exit(1)

    out_dir = cfg.out_dir.expanduser() / video_id
    console.print(f"[cyan]cutting {len(picks)} clip(s)[/cyan] -> {out_dir}")
    clip_paths = cut_all_clips(mp4_path, transcript, picks, out_dir, cfg)
    console.print(f"[green]done[/green]: {len(clip_paths)} clip(s) in {out_dir}")


@app.command("reframe")
def reframe_cmd(
    video_id: str = typer.Argument(..., help="Video ID (folder name in work/ and out/)"),
    clips: list[str] = typer.Argument(..., help="Clip identifiers e.g. clip_01 clip_03"),
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Re-cut selected clips in stacked layout (webcam top, gameplay bottom) -> out/<id>/stacked/."""
    _setup_logging(verbose)
    cfg = load_config(_resolve_config(config_path))
    cfg.reframe.mode = "stacked"

    if not cfg.reframe.webcam_rect:
        console.print("[yellow]Warning:[/yellow] reframe.webcam_rect not set in config — top panel will use center-crop.")

    work_dir = cfg.work_dir.expanduser()
    vod_dir = work_dir / video_id
    stacked_dir = cfg.out_dir.expanduser() / video_id / "stacked"

    picks_path = vod_dir / "picks.json"
    if not picks_path.exists():
        console.print(f"[red]picks.json not found:[/red] {picks_path}")
        raise typer.Exit(1)

    raw = json.loads(picks_path.read_text(encoding="utf-8"))
    all_picks = [
        PickResult(
            candidate=CandidateMoment(**p["candidate"]),
            pick=ClipPick.from_dict(p["pick"]),
        )
        for p in raw
    ]

    transcript_path = vod_dir / "transcript.json"
    if not transcript_path.exists():
        console.print(f"[red]transcript.json not found:[/red] {transcript_path}")
        raise typer.Exit(1)

    from .transcribe import Transcript
    transcript = Transcript.from_json(transcript_path.read_text(encoding="utf-8"))

    mp4_path = vod_dir / f"{video_id}.mp4"
    if not mp4_path.exists():
        console.print(f"[red]MP4 not found:[/red] {mp4_path}")
        raise typer.Exit(1)

    from .detect import load_or_detect_webcam_rect
    load_or_detect_webcam_rect(mp4_path, vod_dir, cfg.reframe)

    # Parse clip identifiers → 1-based indices into all_picks
    selected: list[tuple[int, PickResult]] = []
    for ident in clips:
        parts = ident.split("_")
        if len(parts) < 2 or not parts[1].isdigit():
            console.print(f"[red]Cannot parse clip number from:[/red] {ident!r}  (expected format: clip_01)")
            raise typer.Exit(1)
        idx = int(parts[1])
        if idx < 1 or idx > len(all_picks):
            console.print(f"[red]Clip index {idx} out of range[/red] (picks.json has {len(all_picks)} entries)")
            raise typer.Exit(1)
        selected.append((idx, all_picks[idx - 1]))

    stacked_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[cyan]cutting {len(selected)} stacked clip(s)[/cyan] -> {stacked_dir}")
    for idx, pr in selected:
        slug = _title_slug(pr.pick.title_es)
        out_path = stacked_dir / f"clip_{idx:02d}_{slug}.mp4"
        _cut_one(mp4_path, transcript, pr, idx, out_path, cfg)

    console.print(f"[green]done[/green]: {len(selected)} stacked clip(s) in {stacked_dir}")


@app.command("whoami")
def whoami(
    login: str = typer.Argument(..., help="Twitch login to resolve"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sanity check: resolve a Twitch login to a user id via Helix."""
    _setup_logging(verbose)
    secrets = load_secrets()
    with TwitchClient(secrets.twitch_client_id, secrets.twitch_client_secret) as tc:
        user_id = tc.get_user_id(login)
        console.print(f"{login} -> user_id={user_id}")


@app.command("detect-webcam")
def detect_webcam_cmd(
    video_id: str = typer.Argument(..., help="Video ID (folder name in work/)"),
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    samples: int = typer.Option(20, "--samples", help="Number of frames to sample"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Auto-detect the webcam/face rectangle from sampled frames using Haar cascade detection."""
    _setup_logging(verbose)
    cfg = load_config(_resolve_config(config_path))
    mp4 = cfg.work_dir.expanduser() / video_id / f"{video_id}.mp4"

    if not mp4.exists():
        console.print(f"[red]MP4 not found:[/red] {mp4}")
        raise typer.Exit(1)

    console.print(f"[cyan]Sampling {samples} frames from[/cyan] {mp4.name} ...")

    from .detect import detect_webcam_rect
    try:
        rect = detect_webcam_rect(mp4, sample_count=samples)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    if rect is None:
        console.print(
            "[yellow]No stable face detected.[/yellow] "
            "Try --samples 40, or set webcam_rect manually in config.yaml."
        )
        raise typer.Exit(1)

    x, y, w, h = rect
    console.print(f"\n[green]Detected webcam rect:[/green]  x={x}  y={y}  w={w}  h={h}")
    console.print("\n[bold]Paste into config.yaml:[/bold]")
    console.print(f"  webcam_rect: [{x}, {y}, {w}, {h}]")
    console.print(
        "\n[dim]Tip: increase w/h by ~20% to add padding around the face, "
        "then re-run `clipsmith reframe` to verify.[/dim]"
    )


if __name__ == "__main__":
    app()
