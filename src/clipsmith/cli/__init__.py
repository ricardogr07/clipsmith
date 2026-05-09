"""clipsmith CLI entry point."""

from __future__ import annotations

import typer

from .clip import clip_cmd, reframe_cmd
from .cloud import cloud_app
from .run import process, run_vod, serve, watch, whoami
from .setup import check_ollama, detect_webcam_cmd, setup

app = typer.Typer(add_completion=False, help="Twitch -> AI clip pipeline")

app.add_typer(cloud_app, name="cloud")

app.command()(process)
app.command()(watch)
app.command("run-vod")(run_vod)
app.command()(whoami)
app.command()(serve)
app.command("clip")(clip_cmd)
app.command("reframe")(reframe_cmd)
app.command()(setup)
app.command("check-ollama")(check_ollama)
app.command("detect-webcam")(detect_webcam_cmd)

if __name__ == "__main__":
    app()
