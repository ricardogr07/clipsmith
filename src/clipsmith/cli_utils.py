"""Shared CLI utilities: config resolution and time parsing."""

from __future__ import annotations

import sys
from pathlib import Path

import typer


def _resolve_config(explicit: Path) -> Path:
    """Return config path: explicit arg > bundled next to exe > cwd default."""
    if explicit != Path("config.yaml"):
        return explicit
    bundled = Path(sys.executable).parent / "config.yaml"
    if bundled.exists():
        return bundled
    return explicit


def _parse_start_at(value: str | None) -> float:
    """Parse --start-at value to seconds. Accepts 'MM:SS', 'H:MM:SS', or plain seconds."""
    if value is None:
        return 0.0
    parts = value.strip().split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        pass
    raise typer.BadParameter(f"Cannot parse time {value!r}. Use MM:SS, H:MM:SS, or seconds.")
