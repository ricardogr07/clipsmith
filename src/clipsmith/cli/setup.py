"""CLI command handlers: setup, check-ollama, detect-webcam."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess  # nosec B403
import sys
import webbrowser
from pathlib import Path

import typer
from rich.console import Console

from .utils import _resolve_config
from ..rendering.clipper import _find_ffmpeg
from ..rendering.detect import detect_webcam_rect
from ..pipeline import _setup_logging
from ..settings import load_config

console = Console()
log = logging.getLogger(__name__)


def _patch_webcam_rect_in_config(config_path: Path, rect: list[int]) -> None:
    """Replace the webcam_rect line in config.yaml in-place, preserving all other content."""
    rect_str = f"[{', '.join(str(v) for v in rect)}]"
    text = config_path.read_text(encoding="utf-8")
    new_line = f"  webcam_rect: {rect_str}"
    patched, n = re.subn(r"^(\s*webcam_rect\s*:).*$", new_line, text, flags=re.MULTILINE)
    if n == 0:
        patched = re.sub(
            r"^(reframe\s*:.*)$",
            rf"\1\n{new_line}",
            text,
            flags=re.MULTILINE,
        )
    config_path.write_text(patched, encoding="utf-8")


def setup(
    provider: str | None = typer.Option(
        None, "--provider", help="LLM provider: anthropic, openai, or ollama"
    ),
    key: str | None = typer.Option(
        None, "--key", help="API key (omit to be prompted interactively; not needed for ollama)"
    ),
    model: str | None = typer.Option(
        None, "--model", help="Ollama model to pull (default: llama3.1:8b)"
    ),
) -> None:
    """First-run wizard: configure LLM provider, save API key, verify ffmpeg."""
    env_path = Path(sys.executable).parent / ".env"

    if provider is None:
        provider = (
            typer.prompt(
                "LLM provider",
                default="ollama",
                prompt_suffix=" (anthropic/openai/ollama): ",
            )
            .strip()
            .lower()
        )

    if provider not in ("anthropic", "openai", "ollama"):
        console.print(
            f"[red]Unknown provider:[/red] {provider}. Choose anthropic, openai, or ollama."
        )
        raise typer.Exit(1)

    # ── Ollama path ───────────────────────────────────────────────────────────
    if provider == "ollama":
        ollama_model = model or "llama3.1:8b"

        if shutil.which("ollama"):
            console.print("[green]OK[/green]  ollama is installed")
        else:
            console.print(
                "[yellow]ollama app not found.[/yellow]\n"
                "  Opening download page: https://ollama.com/download\n"
                "  Install it, then re-run: clipsmith setup --provider ollama"
            )
            webbrowser.open("https://ollama.com/download")
            raise typer.Exit(1)

        try:
            import ollama as _ol  # noqa: F401

            console.print("[green]OK[/green]  ollama Python client installed")
        except ImportError:
            console.print(
                "[yellow]ollama Python client not found.[/yellow]\n"
                '  Run: pip install ".[ollama]"  then re-run setup.'
            )
            raise typer.Exit(1)

        console.print(
            f"[cyan]Pulling model[/cyan] [bold]{ollama_model}[/bold] "
            f"(this may take a while on first run)..."
        )
        result = subprocess.run(["ollama", "pull", ollama_model])  # nosec B603 — model name is from config, not user input
        if result.returncode != 0:
            console.print(
                f"[red]ollama pull failed.[/red] Try manually: ollama pull {ollama_model}"
            )
            raise typer.Exit(1)
        console.print(f"[green]OK[/green]  model {ollama_model} ready")

        cfg_path = _resolve_config(Path("config.yaml"))
        if cfg_path.exists():
            text = cfg_path.read_text(encoding="utf-8")
            text, _ = re.subn(
                r"^(\s*)provider\s*:.*$", r"\1provider: ollama", text, flags=re.MULTILINE
            )
            cfg_path.write_text(text, encoding="utf-8")
            console.print(f"[green]OK[/green]  set provider: ollama in {cfg_path}")

    # ── Cloud provider path ───────────────────────────────────────────────────
    else:
        if key is None:
            key = typer.prompt(f"Paste your {provider} API key", hide_input=True).strip()

        if not key:
            console.print("[red]No key provided. Aborting.[/red]")
            raise typer.Exit(1)

        env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"

        existing: list[str] = []
        if env_path.exists():
            existing = env_path.read_text(encoding="utf-8").splitlines()
        updated = [ln for ln in existing if not ln.startswith(f"{env_var}=")]
        updated.append(f"{env_var}={key}")
        env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
        console.print(f"[green]OK[/green]  saved {env_var} to {env_path}")

    # ── ffmpeg check (all providers) ──────────────────────────────────────────
    ffmpeg = _find_ffmpeg()
    if Path(ffmpeg).exists() or shutil.which(ffmpeg):
        console.print(f"[green]OK[/green]  ffmpeg found: {ffmpeg}")
    else:
        console.print(
            "[yellow]ffmpeg not found.[/yellow] "
            "Place ffmpeg.exe in the same folder as clipsmith.exe."
        )

    console.print("\n[bold]Ready.[/bold] Run: clipsmith process path\\to\\video.mp4")


def check_ollama(
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
) -> None:
    """Check whether the ollama Python client, server, and configured model are all ready."""
    cfg = load_config(_resolve_config(config_path))
    model_name = cfg.llm.model_ollama
    ok = True

    try:
        import ollama  # noqa: F401

        console.print("[green]OK[/green]  ollama Python package installed")
    except ImportError:
        console.print('[red]FAIL[/red]  ollama package not found — run: pip install ".[ollama]"')
        raise typer.Exit(1)

    try:
        import ollama as _ol

        models_resp = _ol.list()
        console.print("[green]OK[/green]  ollama server is running (localhost:11434)")
    except Exception as exc:
        console.print(
            f"[red]FAIL[/red]  ollama server not reachable ({exc})\n"
            "    Start it with: ollama serve   (or open the Ollama desktop app)"
        )
        raise typer.Exit(1)

    available = [m.model for m in (models_resp.models or []) if m.model]
    match = any(m == model_name or m.split(":")[0] == model_name.split(":")[0] for m in available)
    if match:
        console.print(f"[green]OK[/green]  model [bold]{model_name}[/bold] is downloaded")
    else:
        console.print(
            f"[red]FAIL[/red]  model [bold]{model_name}[/bold] not found locally.\n"
            f"    Pull it with: ollama pull {model_name}"
        )
        if available:
            console.print(f"    Available models: {', '.join(available)}")
        ok = False

    if ok:
        console.print(
            f"\n[bold green]All good![/bold green] "
            f"Set [cyan]provider: ollama[/cyan] in config.yaml and clipsmith will use "
            f"[bold]{model_name}[/bold] for clip selection."
        )
    else:
        raise typer.Exit(1)


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

    resolved = _resolve_config(config_path)
    _patch_webcam_rect_in_config(resolved, rect)
    console.print(f"[green]Saved[/green] webcam_rect to {resolved}")
    console.print(
        "\n[dim]Tip: increase w/h by ~20% to add padding around the face, "
        "then re-run `clipsmith reframe` to verify.[/dim]"
    )
