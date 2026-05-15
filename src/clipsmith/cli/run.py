"""CLI command handlers: process, watch, run-vod, whoami."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import typer
from rich.console import Console

from .utils import _parse_start_at, _resolve_config
from ..models.twitch import Video
from ..pipeline import process_vod
from ..logging import configure_logging
from ..settings import load_config, load_secrets
from ..twitch.state import State
from ..twitch.client import TwitchClient
from ..twitch.watcher import watch as watch_iter

console = Console()
log = logging.getLogger(__name__)


def process(
    mp4: Path = typer.Argument(..., help="Path to a local MP4 file to process"),
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    provider: str | None = typer.Option(
        None, "--provider", help="Override LLM provider (anthropic|openai)"
    ),
    captions: bool | None = typer.Option(
        None, "--captions/--no-captions", help="Burn captions into video (overrides config)"
    ),
    reframe: bool | None = typer.Option(
        None, "--reframe/--no-reframe", help="Reframe to 9:16 vertical (overrides config)"
    ),
    skip_transcribe: bool = typer.Option(
        False, "--skip-transcribe", help="Use cached transcript.json if it exists"
    ),
    start_at: str | None = typer.Option(
        None, "--start-at", help="Skip content before this timestamp (MM:SS, H:MM:SS, or seconds)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    json_logs: bool = typer.Option(False, "--json-logs", help="Emit newline-delimited JSON logs"),
    resume: bool = typer.Option(
        False, "--resume/--no-resume", help="Skip stages that already completed"
    ),
) -> None:
    """Process a local MP4 through the full pipeline: transcribe -> LLM -> clips."""
    configure_logging(verbose=verbose, json_logs=json_logs)

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
        process_vod(
            video,
            cfg,
            secrets,
            skip_download=True,
            skip_transcribe=skip_transcribe,
            skip_chat=True,
            provider=provider,
            start_s=_parse_start_at(start_at),
            resume=resume,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)


def watch(
    channel: str | None = typer.Argument(None, help="Override config channel(s)"),
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    once: bool = typer.Option(False, "--once", help="Single poll pass, then exit"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Poll Twitch for new archive VODs and run the full pipeline for each."""
    configure_logging(verbose=verbose)
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
            process_vod(event.video, cfg, secrets)
        except Exception as exc:
            log.exception("pipeline failed for VOD %s", event.video.id)
            console.print(f"[red]error — VOD {event.video.id} skipped:[/red] {exc}")


def run_vod(
    video_id: str = typer.Argument(..., help="Twitch video (VOD) id"),
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    local: bool = typer.Option(
        False, "--local", help="Skip all Twitch API calls; use manually placed mp4"
    ),
    skip_download: bool = typer.Option(
        False, "--skip-download", help="Use existing mp4 in work dir"
    ),
    skip_transcribe: bool = typer.Option(
        False, "--skip-transcribe", help="Use cached transcript.json"
    ),
    skip_chat: bool = typer.Option(False, "--skip-chat", help="Use cached chat.json"),
    skip_select: bool = typer.Option(False, "--skip-select", help="Skip LLM selection step"),
    skip_clip: bool = typer.Option(False, "--skip-clip", help="Skip ffmpeg clipping step"),
    provider: str | None = typer.Option(
        None, "--provider", help="Override LLM provider (anthropic|openai)"
    ),
    captions: bool | None = typer.Option(
        None, "--captions/--no-captions", help="Burn captions into video (overrides config)"
    ),
    reframe: bool | None = typer.Option(
        None, "--reframe/--no-reframe", help="Reframe to 9:16 vertical (overrides config)"
    ),
    max_candidates: int = typer.Option(
        20, "--max-candidates", help="Max candidates to send to LLM"
    ),
    start_at: str | None = typer.Option(
        None, "--start-at", help="Skip content before this timestamp (MM:SS, H:MM:SS, or seconds)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    json_logs: bool = typer.Option(False, "--json-logs", help="Emit newline-delimited JSON logs"),
    resume: bool = typer.Option(
        False, "--resume/--no-resume", help="Skip stages that already completed"
    ),
) -> None:
    """Download, transcribe, score candidates, and select clips via LLM."""
    configure_logging(verbose=verbose, json_logs=json_logs)
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
    elif secrets.twitch_client_id and secrets.twitch_client_secret:
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
    else:
        console.print(
            "[yellow]No Twitch credentials — VOD metadata unavailable, proceeding with ID only.[/yellow]"
        )
        video = Video(
            id=video_id,
            user_id="",
            user_login="unknown",
            title=video_id,
            created_at="",
            published_at="",
            url=f"https://www.twitch.tv/videos/{video_id}",
            duration="",
            type="archive",
        )

    try:
        process_vod(
            video,
            cfg,
            secrets,
            skip_download=skip_download,
            skip_transcribe=skip_transcribe,
            skip_chat=skip_chat,
            skip_select=skip_select,
            skip_clip=skip_clip,
            provider=provider,
            max_candidates=max_candidates,
            start_s=_parse_start_at(start_at),
            resume=resume,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)


def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Bind host"),  # nosec B104
    port: int = typer.Option(8000, "--port", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes (dev only)"),
) -> None:
    """Start the clipsmith REST API server (requires [server] extra)."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn not installed.[/red] Run: pip install 'clipsmith-ai[server]'")
        raise typer.Exit(1)

    console.print(f"[green]clipsmith API[/green] → http://{host}:{port}/docs")
    uvicorn.run("clipsmith.api.app:app", host=host, port=port, reload=reload)


def whoami(
    login: str = typer.Argument(..., help="Twitch login to resolve"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sanity check: resolve a Twitch login to a user id via Helix."""
    configure_logging(verbose=verbose)
    secrets = load_secrets()
    with TwitchClient(secrets.twitch_client_id, secrets.twitch_client_secret) as tc:
        user_id = tc.get_user_id(login)
        console.print(f"{login} -> user_id={user_id}")
