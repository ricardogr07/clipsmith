"""clipsmith CLI: `watch`, `run-vod`, `clip`, `whoami`."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler

from .candidates import CandidateMoment, build_candidates, save_candidates
from .chat import download_chat
from .clipper import cut_all_clips
from .downloader import download_vod
from .llm import get_provider
from .llm.base import ClipPick
from .selector import PickResult, build_stream_context, save_picks, select_clips
from .settings import AppConfig, Secrets, load_config, load_secrets
from .state import State
from .transcribe import Transcript, transcribe
from .twitch_client import TwitchClient, Video
from .watcher import watch as watch_iter

app = typer.Typer(add_completion=False, help="Twitch -> AI clip pipeline")
console = Console()
log = logging.getLogger(__name__)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )


def _process_vod(
    video: Video,
    cfg: AppConfig,
    secrets: Secrets,
    *,
    skip_download: bool = False,
    skip_transcribe: bool = False,
    skip_chat: bool = False,
    skip_select: bool = False,
    skip_clip: bool = False,
    provider: str | None = None,
    max_candidates: int = 20,
) -> None:
    """Run the full pipeline for one VOD: download → transcribe → candidates → select → clip."""
    video_id = video.id
    work_dir = cfg.work_dir.expanduser()
    vod_dir = work_dir / video_id
    vod_dir.mkdir(parents=True, exist_ok=True)

    with TwitchClient(secrets.twitch_client_id, secrets.twitch_client_secret) as tc:
        existing_clips = tc.get_clips_for_vod(video.user_id, video_id)

    console.print(
        f"VOD [bold]{video_id}[/bold]: {video.title!r} by {video.user_login} "
        f"({video.duration}, type={video.type}) — {len(existing_clips)} existing clip(s)"
    )

    if not skip_download:
        console.print("[cyan]downloading...[/cyan]")
        result = download_vod(video_id, work_dir)
        mp4_path = result.mp4_path
    else:
        mp4_path = vod_dir / f"{video_id}.mp4"
        if not mp4_path.exists():
            raise FileNotFoundError(f"Expected MP4 not found: {mp4_path}")

    console.print(f"[cyan]transcribing[/cyan] {mp4_path.name} ...")
    transcript = transcribe(
        mp4_path,
        video_id,
        cfg.transcribe,
        overwrite=not skip_transcribe,
    )
    console.print(
        f"[green]transcript done[/green]: {len(transcript.segments)} segments, "
        f"language={transcript.language}"
    )

    console.print("[cyan]downloading chat...[/cyan]")
    chat = download_chat(video_id, work_dir, overwrite=not skip_chat)
    console.print(f"[green]chat loaded[/green]: {len(chat.messages)} messages")

    console.print("[cyan]scoring candidates...[/cyan]")
    candidates = build_candidates(chat, existing_clips, cfg.candidates)
    save_candidates(candidates, vod_dir / "candidates.json")
    console.print(f"[green]candidates[/green]: {len(candidates)} moments")
    for i, c in enumerate(candidates[:10], 1):
        console.print(
            f"  #{i:2d}  t={c.t_center:7.1f}s  score={c.score:6.1f}  "
            f"signals={','.join(c.sources)}"
        )

    if skip_select:
        console.print("[yellow]LLM selection skipped (--skip-select)[/yellow]")
        return

    if provider:
        cfg.llm.provider = provider  # type: ignore[assignment]

    console.print(
        f"[cyan]selecting clips[/cyan] via {cfg.llm.provider} "
        f"(top {max_candidates} candidates)..."
    )
    picker = get_provider(cfg, secrets)
    stream_context = build_stream_context(
        channel=video.user_login,
        vod_title=video.title,
        vod_duration=video.duration,
    )
    picks = select_clips(
        candidates, transcript, picker, stream_context, cfg.clip,
        max_candidates=max_candidates,
    )
    picks_path = vod_dir / "picks.json"
    save_picks(picks, picks_path)
    console.print(f"[green]picks[/green]: {len(picks)} accepted → {picks_path}")
    for i, pr in enumerate(picks, 1):
        console.print(
            f"  #{i:2d}  [{pr.pick.start_offset_s:.1f}–{pr.pick.end_offset_s:.1f}s]  "
            f"{pr.pick.title_es!r}"
        )

    if skip_clip:
        console.print("[yellow]clipping skipped (--skip-clip)[/yellow]")
        return

    out_dir = cfg.out_dir.expanduser() / video_id
    console.print(f"[cyan]cutting clips[/cyan] → {out_dir}")
    clip_paths = cut_all_clips(mp4_path, transcript, picks, out_dir, cfg)
    console.print(f"[green]done[/green]: {len(clip_paths)} clip(s) in {out_dir}")


# ── commands ──────────────────────────────────────────────────────────────────

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
    skip_download: bool = typer.Option(False, "--skip-download", help="Use existing mp4 in work dir"),
    skip_transcribe: bool = typer.Option(False, "--skip-transcribe", help="Use cached transcript.json"),
    skip_chat: bool = typer.Option(False, "--skip-chat", help="Use cached chat.json"),
    skip_select: bool = typer.Option(False, "--skip-select", help="Skip LLM selection step"),
    skip_clip: bool = typer.Option(False, "--skip-clip", help="Skip ffmpeg clipping step"),
    provider: str | None = typer.Option(None, "--provider", help="Override LLM provider (anthropic|openai)"),
    max_candidates: int = typer.Option(20, "--max-candidates", help="Max candidates to send to LLM"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Download, transcribe, score candidates, and select clips via LLM."""
    _setup_logging(verbose)
    cfg = load_config(config_path)
    secrets = load_secrets()

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
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Re-run the ffmpeg clipper from an existing picks.json (no LLM re-call)."""
    _setup_logging(verbose)
    cfg = load_config(config_path)

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
    console.print(f"[cyan]cutting {len(picks)} clip(s)[/cyan] → {out_dir}")
    clip_paths = cut_all_clips(mp4_path, transcript, picks, out_dir, cfg)
    console.print(f"[green]done[/green]: {len(clip_paths)} clip(s) in {out_dir}")


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


if __name__ == "__main__":
    app()
