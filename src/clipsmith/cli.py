"""clipsmith CLI entry point."""

from __future__ import annotations

import typer

from .cli_clip import clip_cmd, reframe_cmd
from .cli_run import process, run_vod, watch, whoami
from .cli_setup import check_ollama, detect_webcam_cmd, setup

app = typer.Typer(add_completion=False, help="Twitch -> AI clip pipeline")

app.command()(process)
app.command()(watch)
app.command("run-vod")(run_vod)
app.command()(whoami)
app.command("clip")(clip_cmd)
app.command("reframe")(reframe_cmd)
app.command()(setup)
app.command("check-ollama")(check_ollama)
app.command("detect-webcam")(detect_webcam_cmd)

if __name__ == "__main__":
    app()
