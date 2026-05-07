"""Candidate moment domain model."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class CandidateMoment:
    t_center: float  # seconds into VOD
    score: float
    sources: list[str]  # human-readable signal labels
    reasons: list[str]  # detail strings for the LLM prompt

    def to_dict(self) -> dict:
        return asdict(self)
