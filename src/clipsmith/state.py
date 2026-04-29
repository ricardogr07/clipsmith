"""Tiny on-disk JSON state so the watcher doesn't re-process VODs across restarts."""

from __future__ import annotations

import json
from pathlib import Path


class State:
    def __init__(self, path: str | Path = "state.json"):
        self.path = Path(path)
        self._data: dict = {"seen_video_ids": []}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        self._data.setdefault("seen_video_ids", [])

    @property
    def seen(self) -> set[str]:
        return set(self._data["seen_video_ids"])

    def mark_seen(self, video_id: str) -> None:
        ids = self._data["seen_video_ids"]
        if video_id not in ids:
            ids.append(video_id)
            self._save()

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
