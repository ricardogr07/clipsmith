"""clipsmith CLI: `watch`, `run-vod`, `clip` (later phases)."""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler

from .settings import load_config, load_secrets
from .state import State
from .twitch_client import TwitchClient
from .watcher import watch as watch_iter

app = typer.Typer(add_completion=False, help="Twitch -> AI clip pipeline")
console = Console()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )


@app.command()
def watch(
    channel: str | None = typer.Argument(None, help="Override config channel(s)"),
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    once: bool = typer.Option(False, "--once", help="Single poll pass, then exit"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Poll Twitch for new archive VODs and print events."""
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
            f"[green]new VOD detected[/green]: id={event.video.id} "
            f"channel={event.channel} title={event.video.title!r} "
            f"duration={event.video.duration} url={event.video.url}"
        )


@app.command("run-vod")
def run_vod(
    video_id: str = typer.Argument(..., help="Twitch video (VOD) id"),
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """End-to-end pipeline for a single VOD. Phase 1 stub: prints VOD metadata."""
    _setup_logging(verbose)
    _ = load_config(config_path)
    secrets = load_secrets()
    with TwitchClient(secrets.twitch_client_id, secrets.twitch_client_secret) as tc:
        body = tc._get("/videos", {"id": video_id})  # noqa: SLF001
        data = body.get("data") or []
        if not data:
            console.print(f"[red]VOD not found:[/red] {video_id}")
            raise typer.Exit(1)
        v = data[0]
        console.print(
            f"VOD {v['id']}: {v['title']!r} by {v['user_login']} "
            f"({v['duration']}, type={v['type']})"
        )
    console.print("[yellow]pipeline stages download/transcribe/clip not implemented yet[/yellow]")


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
