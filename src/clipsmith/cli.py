"""clipsmith CLI: `watch`, `run-vod`, `clip`, `whoami`."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich.console import Console

from .candidates import CandidateMoment
from .clipper import cut_all_clips
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
