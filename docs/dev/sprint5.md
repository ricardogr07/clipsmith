# Sprint 5 — ML Feedback Loop

## Goal

Turn the clip approval database into a learning signal. Right now approved and rejected clips
sit in SQLite and go nowhere — the pipeline never gets smarter. This sprint closes that loop:
capture which candidate signals fired for each clip at harvest time, expose approval-rate
analytics per signal and per prompt, let users recalibrate signal weights after a review
session, and introduce a second prompt template so two strategies can be compared on real
data.

Four pieces land together because they depend on the same new schema columns: `signal_breakdown`
and `prompt_version`. The analytics routes, calibration endpoint, and dashboard prompt-selector
all read those columns.

---

## Step 0 — Doc Pre-flight

Update the plan before starting implementation.

### `docs/dev/PLAN.md`

| Item | Change |
|------|--------|
| Sprint 5 status | `🔜 Next` → `🚧 In Progress` |

### Acceptance

- `PLAN.md` sprint map shows Sprint 5 `🚧 In Progress`
- `mkdocs build --strict` exits 0

---

## Step 1 — Schema: Two New Columns

Add `signal_breakdown` (JSON) to `Clip` and `prompt_version` to `Run`.

### `src/clipsmith/db/models.py`

```python
from sqlalchemy import JSON

class Run(Base):
    # ... existing fields ...
    prompt_version: Mapped[str] = mapped_column(String(32), default="v1")

class Clip(Base):
    # ... existing fields ...
    signal_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

`signal_breakdown` schema (populated by `_harvest_clips`):

```json
{
  "existing_clip": 100.0,
  "clip_command": 25.0,
  "chat_density": 14.3,
  "transcript_hype": 0.0,
  "audio_energy": 15.0,
  "total_raw": 154.3,
  "normalized": 87.4
}
```

Update `Clip.to_dict()` to include `signal_breakdown` and `prompt_version` in `Run.to_dict()`.

---

## Step 2 — Capture Signal Breakdown at Harvest

The pipeline already produces `candidates.json` with `sources` and a raw `score` per moment.
Extend `_harvest_clips` in `worker.py` to also read `candidates.json` and match each pick
to its candidate by `t_center` proximity (within 5 s), then extract per-signal contributions.

### `src/clipsmith/api/worker.py`

Replace the existing `_harvest_clips` with this extended version:

```python
import math

def _harvest_clips(db: Session, run_id: int, vod_id: str, cfg: AppConfig) -> None:
    picks_path = cfg.work_dir.expanduser() / vod_id / "picks.json"
    candidates_path = cfg.work_dir.expanduser() / vod_id / "candidates.json"
    if not picks_path.exists():
        return

    picks_data = json.loads(picks_path.read_text(encoding="utf-8"))

    # Load candidates for signal breakdown matching
    candidates_by_t: list[dict] = []
    if candidates_path.exists():
        candidates_by_t = json.loads(candidates_path.read_text(encoding="utf-8"))

    for i, item in enumerate(picks_data, 1):
        p = item.get("pick", {})
        title = p.get("title_es", "")
        slug = _title_slug(title)
        filename = f"clip_{i:02d}_{slug}.mp4"
        center_s = (p.get("start_offset_s", 0.0) + p.get("end_offset_s", 0.0)) / 2.0

        breakdown = _build_breakdown(center_s, candidates_by_t)
        score = item.get("candidate", {}).get("score", breakdown.get("normalized", 0.0))

        clip = Clip(
            run_id=run_id,
            filename=filename,
            title=title,
            start_s=p.get("start_offset_s", 0.0),
            end_s=p.get("end_offset_s", 0.0),
            score=score,
            signal_breakdown=breakdown,
        )
        db.add(clip)
    db.commit()


def _build_breakdown(center_s: float, candidates: list[dict]) -> dict:
    """Find the closest candidate and decompose its per-signal contributions."""
    if not candidates:
        return {}
    best = min(candidates, key=lambda c: abs(c.get("t_center", 0.0) - center_s))
    if abs(best.get("t_center", 0.0) - center_s) > 5.0:
        return {}  # no close match

    sources: list[str] = best.get("sources", [])
    raw_score: float = best.get("score", 0.0)

    # Approximate per-signal contributions from sources list
    # Real weights come from config; this is a proportional attribution
    signal_weights = {
        "existing_clip": 100.0,
        "clip_command": 25.0,
        "chat_density": 20.0,
        "transcript_hype": 12.0,
        "audio_energy": 15.0,
    }
    total_weight = sum(signal_weights[s] for s in sources if s in signal_weights)
    breakdown: dict[str, float] = {
        s: round(signal_weights.get(s, 0.0), 1) for s in signal_weights
        if s in sources
    }
    breakdown["total_raw"] = round(total_weight, 1)
    breakdown["normalized"] = round(raw_score, 1)
    return breakdown
```

### `src/clipsmith/api/routes/runs.py`

Add `prompt_version` to `RunCreate`:

```python
class RunCreate(BaseModel):
    vod_id: str
    channel: str = ""
    provider: Literal["anthropic", "openai", "ollama"] | None = None
    prompt_version: Literal["v1", "v2"] = "v1"

    @field_validator("vod_id") ...  # unchanged
```

In `create_run`, pass `body.prompt_version` to `start_run` and save it on the `Run` record:

```python
run = Run(
    vod_id=body.vod_id,
    channel=body.channel,
    status=RunStatus.pending,
    prompt_version=body.prompt_version,
)
...
background_tasks.add_task(
    start_run, run.id, body.vod_id, body.channel, body.provider,
    body.prompt_version, request.app
)
```

### `src/clipsmith/api/worker.py`

`start_run` and `_run_pipeline` gain `prompt_version: str = "v1"`. Pass it to the LLM
provider selection so the correct prompt template is used.

```python
def start_run(
    run_id: int, vod_id: str, channel: str, provider: str | None,
    prompt_version: str = "v1", app: Any = None
) -> None: ...

def _run_pipeline(
    db: Session, run_id: int, vod_id: str, channel: str,
    provider: str | None, prompt_version: str = "v1"
) -> None:
    cfg = load_config(Path("config.yaml"))
    ...
    cfg.llm.prompt_version = prompt_version  # consumed by providers
```

---

## Step 3 — Second Prompt Template

Add a `v2` system prompt to `llm/prompts.py`. The v2 prompt is more concise and
emphasises clip momentum over linguistic signals — a meaningful strategic difference
to measure.

### `src/clipsmith/llm/prompts.py`

```python
SYSTEM_PROMPT_V1 = SYSTEM_PROMPT  # existing prompt, aliased

SYSTEM_PROMPT_V2 = """\
You are a Twitch clip editor for short-form video. Select moments that are
immediately engaging with zero setup — reaction moments, unexpected events, or
skill highlights. Avoid anything that requires prior context to understand.

Respond ONLY with valid JSON:
{
  "include": <bool>,
  "start_offset_s": <number>,
  "end_offset_s": <number>,
  "title_es": <string>,   // 3–6 words, Spanish, punchy
  "reason": <string>      // 1 sentence English
}

Rules: clip must be 15–30 s; title must be in Spanish; no markdown.
"""

SYSTEM_PROMPTS: dict[str, str] = {
    "v1": SYSTEM_PROMPT_V1,
    "v2": SYSTEM_PROMPT_V2,
}


def get_system_prompt(version: str = "v1") -> str:
    return SYSTEM_PROMPTS.get(version, SYSTEM_PROMPT_V1)
```

Update all three providers (`anthropic_provider.py`, `openai_provider.py`,
`ollama_provider.py`) to accept `prompt_version: str = "v1"` in their constructor
and call `get_system_prompt(prompt_version)` instead of the bare `SYSTEM_PROMPT` constant.

### `src/clipsmith/config/models.py`

```python
class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model_anthropic: str = "claude-sonnet-4-6"
    model_openai: str = "gpt-4o-mini"
    model_ollama: str = "llama3.1"
    prompt_version: str = "v1"    # NEW
```

---

## Step 4 — Analytics Endpoints

### New file: `src/clipsmith/api/routes/analytics.py`

```python
"""Approval-rate analytics: per signal and per prompt version."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..deps import get_db
from ...db.models import Clip, Run

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/signals", summary="Per-signal approval rates")
def signal_approval_rates(db: Session = Depends(get_db)) -> dict:
    """
    For each candidate signal, return the fraction of clips where that signal
    fired that were subsequently approved. Only includes clips that have been
    reviewed (approved is not null) and have a signal_breakdown recorded.

    Returns:
        {
          "existing_clip": {"approved": 12, "rejected": 2, "rate": 0.857},
          "chat_density":  {"approved": 8,  "rejected": 5, "rate": 0.615},
          ...
        }
    """
    reviewed = (
        db.execute(
            select(Clip).where(
                Clip.approved.is_not(None),
                Clip.signal_breakdown.is_not(None),
            )
        )
        .scalars()
        .all()
    )

    signal_names = [
        "existing_clip", "clip_command", "chat_density",
        "transcript_hype", "audio_energy",
    ]
    stats: dict[str, dict] = {s: {"approved": 0, "rejected": 0} for s in signal_names}

    for clip in reviewed:
        bd = clip.signal_breakdown or {}
        for sig in signal_names:
            if sig in bd and bd[sig] > 0:
                if clip.approved:
                    stats[sig]["approved"] += 1
                else:
                    stats[sig]["rejected"] += 1

    for sig, counts in stats.items():
        total = counts["approved"] + counts["rejected"]
        counts["rate"] = round(counts["approved"] / total, 3) if total else None

    return stats


@router.get("/prompts", summary="Approval rates by prompt version")
def prompt_approval_rates(db: Session = Depends(get_db)) -> dict:
    """
    Return approval rates grouped by prompt_version and provider.

    Returns:
        {
          "v1": {
            "anthropic": {"approved": 10, "rejected": 3, "rate": 0.769},
            "openai":    {"approved": 4,  "rejected": 2, "rate": 0.667}
          },
          "v2": { ... }
        }
    """
    rows = (
        db.execute(
            select(Run.prompt_version, Run.id)
            .where(Run.prompt_version.is_not(None))
        )
        .all()
    )

    # Map run_id → prompt_version
    run_to_version: dict[int, str] = {row[1]: row[0] for row in rows}

    reviewed_clips = (
        db.execute(
            select(Clip, Run)
            .join(Run, Clip.run_id == Run.id)
            .where(Clip.approved.is_not(None))
        )
        .all()
    )

    result: dict[str, dict] = {}
    for clip, run in reviewed_clips:
        version = run_to_version.get(run.id, "v1")
        provider = run.channel or "unknown"  # channel stores display info; use provider field later
        result.setdefault(version, {}).setdefault(
            provider, {"approved": 0, "rejected": 0}
        )
        key = "approved" if clip.approved else "rejected"
        result[version][provider][key] += 1

    for version, providers in result.items():
        for provider, counts in providers.items():
            total = counts["approved"] + counts["rejected"]
            counts["rate"] = round(counts["approved"] / total, 3) if total else None

    return result
```

### `src/clipsmith/api/app.py`

```python
from .routes import analytics, clips, files, health, publish, runs, stream

app.include_router(analytics.router)
```

---

## Step 5 — Weight Calibration Endpoint

After a user reviews a run, the calibration endpoint reads the current approval rates and
writes updated signal weights back to `config.yaml` using an exponential moving average
(EMA) so single outlier runs don't swing the weights too far.

### New route in `src/clipsmith/api/routes/analytics.py`

```python
import yaml
from pathlib import Path


@router.post("/runs/{run_id}/calibrate", summary="Recalibrate signal weights from approvals")
def calibrate_weights(run_id: int, db: Session = Depends(get_db)) -> dict:
    """
    After the user has approved/rejected clips for a run, recompute signal weights
    using a 0.3-alpha EMA blend of the historical approval rate into the current
    configured weights. Writes the result to config.yaml.

    Returns the new weight values.
    """
    # Get clips for this run with breakdown + review
    clips_q = (
        db.execute(
            select(Clip).where(
                Clip.run_id == run_id,
                Clip.approved.is_not(None),
                Clip.signal_breakdown.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    if not clips_q:
        return {"message": "No reviewed clips with signal breakdown for this run", "weights": {}}

    SIGNAL_CONFIG_KEYS = {
        "existing_clip": "existing_clip_boost",
        "clip_command": "clip_command_boost",
        "chat_density": None,          # density is proportional, no direct boost key
        "transcript_hype": "transcript_hype_score",
        "audio_energy": "audio_energy_boost",
    }
    DEFAULTS = {
        "existing_clip_boost": 100.0,
        "clip_command_boost": 25.0,
        "transcript_hype_score": 12.0,
        "audio_energy_boost": 15.0,
    }
    ALPHA = 0.3  # EMA blend factor

    # Compute per-signal approval rate for this run
    signal_approved: dict[str, int] = {}
    signal_total: dict[str, int] = {}
    for clip in clips_q:
        bd = clip.signal_breakdown or {}
        for sig, cfg_key in SIGNAL_CONFIG_KEYS.items():
            if cfg_key is None or sig not in bd or bd[sig] <= 0:
                continue
            signal_total[cfg_key] = signal_total.get(cfg_key, 0) + 1
            if clip.approved:
                signal_approved[cfg_key] = signal_approved.get(cfg_key, 0) + 1

    # Load current config
    cfg_path = Path("config.yaml")
    with cfg_path.open() as f:
        cfg_data = yaml.safe_load(f)

    candidates_cfg: dict = cfg_data.setdefault("candidates", {})
    new_weights: dict[str, float] = {}

    for key, default in DEFAULTS.items():
        current = float(candidates_cfg.get(key, default))
        total = signal_total.get(key, 0)
        if total == 0:
            new_weights[key] = current
            continue
        approval_rate = signal_approved.get(key, 0) / total
        # EMA: blend current weight toward approval-rate-scaled default
        target = default * (0.5 + approval_rate)  # rate=1.0 → 1.5×default; rate=0.0 → 0.5×default
        new_val = round((1 - ALPHA) * current + ALPHA * target, 2)
        new_weights[key] = new_val
        candidates_cfg[key] = new_val

    with cfg_path.open("w") as f:
        yaml.dump(cfg_data, f, allow_unicode=True, sort_keys=False)

    return {"weights": new_weights, "run_id": run_id}
```

---

## File Layout (final state after Sprint 5)

```
src/clipsmith/
├── db/
│   └── models.py              MODIFIED — Clip.signal_breakdown (JSON); Run.prompt_version
├── api/
│   ├── app.py                 MODIFIED — include analytics router
│   ├── worker.py              MODIFIED — _harvest_clips captures breakdown; start_run gains prompt_version
│   └── routes/
│       ├── runs.py            MODIFIED — RunCreate gains prompt_version field
│       └── analytics.py       NEW — /analytics/signals, /analytics/prompts, /runs/{id}/calibrate
├── llm/
│   ├── prompts.py             MODIFIED — SYSTEM_PROMPT_V2, SYSTEM_PROMPTS dict, get_system_prompt()
│   ├── anthropic_provider.py  MODIFIED — accepts prompt_version, calls get_system_prompt()
│   ├── openai_provider.py     MODIFIED — same
│   └── ollama_provider.py     MODIFIED — same
└── config/
    └── models.py              MODIFIED — LLMConfig gains prompt_version field
```

---

## Verification Checklist

### Schema
- [ ] `Clip.signal_breakdown` is present and nullable in the DB after `alembic upgrade head` (or `create_all`)
- [ ] `Run.prompt_version` defaults to `"v1"` for existing rows
- [ ] `Clip.to_dict()` includes `signal_breakdown`; `Run.to_dict()` includes `prompt_version`

### Signal Capture
- [ ] After a pipeline run, every `Clip` row has a non-null `signal_breakdown` dict
- [ ] Dict contains only signals that actually fired (no zero-value entries for unfired signals)
- [ ] `_build_breakdown` returns `{}` if no candidate is within 5 s of the pick center

### Prompt A/B
- [ ] `POST /runs {"vod_id": "...", "prompt_version": "v2"}` → run stored with `prompt_version="v2"`
- [ ] `"v3"` → 422 (Literal validation)
- [ ] Anthropic provider uses `SYSTEM_PROMPT_V2` when `prompt_version="v2"`

### Analytics
- [ ] `GET /analytics/signals` → returns per-signal approved/rejected counts and rate
- [ ] Returns `rate: null` for signals with no reviewed clips (not divide-by-zero)
- [ ] `GET /analytics/prompts` → groups by version

### Calibration
- [ ] `POST /analytics/runs/{id}/calibrate` with reviewed run → returns `{"weights": {...}}`
- [ ] `config.yaml` `candidates` section updated after calibration
- [ ] Calling twice on same run is idempotent (EMA converges, doesn't explode)
- [ ] Returns `{"message": "..."}` if no reviewed clips with breakdown exist
