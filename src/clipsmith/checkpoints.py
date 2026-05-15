"""Per-stage checkpoint sentinel files for resumable pipeline runs."""

from __future__ import annotations

from pathlib import Path

STAGES = ["download", "transcribe", "chat", "candidates", "select", "render"]


class CheckpointManager:
    """Tracks completed pipeline stages via sentinel files.

    Sentinel files live under: <root>/<vod_id>/<stage>.done
    A sentinel is written only after a stage completes successfully, so a
    stage that fails leaves no sentinel and will re-run on --resume.
    """

    def __init__(self, root: Path, vod_id: str) -> None:
        self.root = root / vod_id
        self.root.mkdir(parents=True, exist_ok=True)

    def is_done(self, stage: str) -> bool:
        """Return True if the stage sentinel file exists."""
        return (self.root / f"{stage}.done").exists()

    def mark_done(self, stage: str) -> None:
        """Write the sentinel file for a completed stage."""
        (self.root / f"{stage}.done").touch()

    def clear(self, stage: str | None = None) -> None:
        """Remove sentinel file(s). Pass stage=None to clear all stages."""
        targets = [stage] if stage else STAGES
        for s in targets:
            p = self.root / f"{s}.done"
            if p.exists():
                p.unlink()
