"""Analytics endpoints: signal performance, prompt A/B comparison, EMA calibration."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db, verify_api_key
from ...db.models import Clip, Run

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/signals", summary="Aggregate signal contribution stats across approved clips")
def signal_stats(db: Session = Depends(get_db)) -> dict:
    """Return per-signal total score and approval counts across all clips with signal_breakdown."""
    clips = db.query(Clip).filter(Clip.signal_breakdown.isnot(None)).all()

    totals: dict[str, float] = defaultdict(float)
    approved_totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    approved_counts: dict[str, int] = defaultdict(int)

    for clip in clips:
        bd = clip.signal_breakdown or {}
        for signal, value in bd.items():
            totals[signal] += value
            counts[signal] += 1
            if clip.approved is True:
                approved_totals[signal] += value
                approved_counts[signal] += 1

    signals = sorted(totals.keys())
    return {
        "signals": [
            {
                "signal": s,
                "clip_count": counts[s],
                "approved_count": approved_counts.get(s, 0),
                "approval_rate": (round(approved_counts[s] / counts[s], 3) if counts[s] else 0.0),
                "total_score": round(totals[s], 2),
            }
            for s in signals
        ]
    }


@router.get("/prompts", summary="Compare clip approval rate by prompt version")
def prompt_comparison(db: Session = Depends(get_db)) -> dict:
    """Return per-prompt-version approval stats across all clips."""
    runs = db.query(Run).all()

    version_clips: dict[str, list[Clip]] = defaultdict(list)
    for run in runs:
        for clip in run.clips:
            version_clips[run.prompt_version].append(clip)

    result = []
    for version, clips in sorted(version_clips.items()):
        reviewed = [c for c in clips if c.approved is not None]
        approved = [c for c in clips if c.approved is True]
        result.append(
            {
                "prompt_version": version,
                "clip_count": len(clips),
                "reviewed_count": len(reviewed),
                "approved_count": len(approved),
                "approval_rate": (round(len(approved) / len(reviewed), 3) if reviewed else None),
            }
        )

    return {"versions": result}


@router.post(
    "/runs/{run_id}/calibrate",
    summary="EMA-calibrate signal weights based on approval outcomes",
    dependencies=[Depends(verify_api_key)],
)
def calibrate_run(run_id: int, db: Session = Depends(get_db)) -> dict:
    """Return EMA-adjusted weight recommendations for each signal based on clip approvals.

    Uses alpha=0.3 exponential moving average over per-signal approval rates.
    This is a read-only recommendation endpoint — it does not modify any config.
    """
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    clips = [c for c in run.clips if c.signal_breakdown and c.approved is not None]
    if not clips:
        raise HTTPException(422, "No reviewed clips with signal data for this run")

    alpha = 0.3
    signal_outcomes: dict[str, list[bool]] = defaultdict(list)
    for clip in clips:
        for signal in clip.signal_breakdown or {}:
            signal_outcomes[signal].append(clip.approved is True)

    weights: list[dict] = []
    for signal, outcomes in sorted(signal_outcomes.items()):
        approval_rate = sum(outcomes) / len(outcomes)
        ema = approval_rate
        for _ in range(len(outcomes) - 1):
            ema = alpha * approval_rate + (1 - alpha) * ema
        weights.append(
            {
                "signal": signal,
                "clip_count": len(outcomes),
                "approval_rate": round(approval_rate, 3),
                "recommended_weight": round(ema, 3),
            }
        )

    return {"run_id": run_id, "alpha": alpha, "weights": weights}
