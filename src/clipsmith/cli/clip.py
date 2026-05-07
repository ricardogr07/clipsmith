"""CLI command handlers: clip, reframe."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich.console import Console

from .utils import _resolve_config
from ..rendering.clipper import _cut_one, _title_slug, cut_all_clips
from ..rendering.detect import load_or_detect_webcam_rect
from ..llm.base import ClipPick
from ..models.candidates import CandidateMoment
from ..models.transcript import Transcript
from ..pipeline import _setup_logging
from ..selection.selector import PickResult
from ..settings import load_config

console = Console()
log = logging.getLogger(__name__)


def clip_cmd(
    video_id: str = typer.Argument(..., help="Twitch video (VOD) id"),
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    captions: bool | None = typer.Option(
        None, "--captions/--no-captions", help="Burn captions into video (overrides config)"
    ),
    reframe: bool | None = typer.Option(
        None, "--reframe/--no-reframe", help="Reframe to 9:16 vertical (overrides config)"
    ),
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
        console.print(
            "[yellow]Warning:[/yellow] reframe.webcam_rect not set in config — top panel will use center-crop."
        )

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

    transcript = Transcript.from_json(transcript_path.read_text(encoding="utf-8"))

    mp4_path = vod_dir / f"{video_id}.mp4"
    if not mp4_path.exists():
        console.print(f"[red]MP4 not found:[/red] {mp4_path}")
        raise typer.Exit(1)

    load_or_detect_webcam_rect(mp4_path, vod_dir, cfg.reframe)

    selected: list[tuple[int, PickResult]] = []
    for ident in clips:
        parts = ident.split("_")
        if len(parts) < 2 or not parts[1].isdigit():
            console.print(
                f"[red]Cannot parse clip number from:[/red] {ident!r}  (expected format: clip_01)"
            )
            raise typer.Exit(1)
        idx = int(parts[1])
        if idx < 1 or idx > len(all_picks):
            console.print(
                f"[red]Clip index {idx} out of range[/red] (picks.json has {len(all_picks)} entries)"
            )
            raise typer.Exit(1)
        selected.append((idx, all_picks[idx - 1]))

    stacked_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[cyan]cutting {len(selected)} stacked clip(s)[/cyan] -> {stacked_dir}")
    for idx, pr in selected:
        slug = _title_slug(pr.pick.title_es)
        out_path = stacked_dir / f"clip_{idx:02d}_{slug}.mp4"
        _cut_one(mp4_path, transcript, pr, idx, out_path, cfg)

    console.print(f"[green]done[/green]: {len(selected)} stacked clip(s) in {stacked_dir}")
