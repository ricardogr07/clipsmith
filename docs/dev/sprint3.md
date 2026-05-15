# Sprint 3 — Observability + Pipeline Reliability

## Goal

Make every pipeline run auditable and fault-tolerant.
Three features land together because they reinforce each other:
**structured logs** (JSON in API mode, pretty in CLI mode) give every event a
machine-readable shape; **stage checkpoints** persist progress to disk so a
crashed run can resume without re-doing expensive work; **LLM retry** wraps
every provider call with exponential backoff so transient rate-limit errors stop
silently dropping candidates.

---

## Step 0 — Doc Pre-flight

Sprint 2 is done. Update the plan doc before starting implementation.

### `docs/dev/PLAN.md`

| Item | Change |
|------|--------|
| Sprint 2 status | `🚧 In Progress` → `✅ Done` |
| Sprint 3 status | `🔜 Next` → `🚧 In Progress` |
| Sprint 3 detail block | Expand to match final scope: structlog, checkpoints, tenacity retry |

### Acceptance

- `PLAN.md` sprint map is accurate
- `mkdocs build --strict` passes with zero warnings

---

## Step 1 — Structured Logging (`structlog`)

Replace `logging.basicConfig` + `RichHandler` with `structlog` so every log
line carries typed key-value context. CLI mode keeps the current pretty output;
API / server mode emits newline-delimited JSON that can be piped to any log
aggregator.

### Dependency

`pyproject.toml` — add to core deps:

```toml
"structlog>=24.1",
```

### New file: `src/clipsmith/logging.py`

```python
import logging
import sys
import structlog

def configure_logging(*, verbose: bool = False, json_logs: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
```

### Canonical log events

Every structured event must include these fields:

| Event key | Required extra fields | When emitted |
|---|---|---|
| `stage_start` | `run_id`, `vod_id`, `stage` | Beginning of each pipeline stage |
| `stage_done` | `run_id`, `vod_id`, `stage`, `elapsed_ms` | After each stage succeeds |
| `stage_skip` | `run_id`, `vod_id`, `stage` | Checkpoint hit — stage bypassed |
| `llm_pick` | `run_id`, `candidate_id`, `provider`, `include`, `score`, `elapsed_ms` | After each `picker.pick()` call |
| `llm_retry` | `run_id`, `candidate_id`, `provider`, `attempt`, `wait_s`, `error` | Before each retry sleep |
| `llm_failed` | `run_id`, `candidate_id`, `provider`, `attempts` | All retries exhausted |
| `checkpoint` | `run_id`, `stage`, `action` | `action` ∈ `{"saved", "restored", "cleared"}` |

### Files modified

| File | Change |
|------|--------|
| `src/clipsmith/pipeline.py` | Replace `_setup_logging()` with `configure_logging()`; bind `run_id` + `vod_id` via `structlog.contextvars.bind_contextvars()` at run start; emit `stage_start` / `stage_done` around each stage |
| `src/clipsmith/api/worker.py` | Call `configure_logging(json_logs=True)` once at startup; bind `run_id` at task start |
| `src/clipsmith/llm/anthropic_provider.py` | Replace `log = logging.getLogger(__name__)` with `log = structlog.get_logger()` |
| `src/clipsmith/llm/openai_provider.py` | Same |
| `src/clipsmith/llm/ollama_provider.py` | Same |
| `src/clipsmith/selection/selector.py` | Log `llm_pick` event after each `picker.pick()` call, including elapsed ms and token usage when available |

### `--json-logs` CLI flag

`src/clipsmith/cli/run.py` — add flag to `process` and `run_vod` commands:

```python
json_logs: bool = typer.Option(False, "--json-logs", help="Emit newline-delimited JSON logs"),
```

Pass `json_logs` into `process_vod()`, which forwards it to `configure_logging()`.

---

## Step 2 — Stage Checkpoints

Persist a sentinel file after each pipeline stage so a crashed or interrupted
run can continue from where it left off using `--resume`.

### New file: `src/clipsmith/checkpoints.py`

```python
from pathlib import Path

STAGES = ["download", "transcribe", "chat", "candidates", "select", "render"]

class CheckpointManager:
    def __init__(self, output_dir: Path, vod_id: str) -> None:
        self.root = output_dir / ".checkpoints" / vod_id
        self.root.mkdir(parents=True, exist_ok=True)

    def is_done(self, stage: str) -> bool:
        return (self.root / f"{stage}.done").exists()

    def mark_done(self, stage: str) -> None:
        (self.root / f"{stage}.done").touch()

    def clear(self, stage: str | None = None) -> None:
        targets = [stage] if stage else STAGES
        for s in targets:
            p = self.root / f"{s}.done"
            if p.exists():
                p.unlink()
```

### Checkpoint stages

| Stage | Sentinel file | What it guards |
|---|---|---|
| `download` | `download.done` | VOD file present on disk |
| `transcribe` | `transcribe.done` | `transcript.json` |
| `chat` | `chat.done` | `chat.json` |
| `candidates` | `candidates.done` | `candidates.json` |
| `select` | `select.done` | `picks.json` |
| `render` | `render.done` | All rendered clip files |

### `pipeline.py` changes

`process_vod()` gains `resume: bool = False` parameter:

```python
ckpt = CheckpointManager(output_dir=cfg.output_dir, vod_id=vod_id)

# Pattern repeated around each stage:
if resume and ckpt.is_done("transcribe"):
    log.info("stage_skip", stage="transcribe")
else:
    # ... run transcription ...
    ckpt.mark_done("transcribe")
    log.info("checkpoint", stage="transcribe", action="saved")
```

Checkpointing is only written on success. A stage that raises will not leave a
sentinel, so the next `--resume` will retry it.

### Config addition

`src/clipsmith/config/models.py` — add to `PipelineConfig`:

```python
class CheckpointConfig(BaseModel):
    enabled: bool = True
    dir: str = ".checkpoints"
```

```python
class PipelineConfig(BaseModel):
    # existing fields ...
    checkpoint: CheckpointConfig = CheckpointConfig()
```

`config.yaml` template addition:

```yaml
pipeline:
  checkpoint:
    enabled: true
    dir: ".checkpoints"
```

### `cli/run.py` changes

```python
resume: bool = typer.Option(False, "--resume/--no-resume", help="Skip stages that already have checkpoints"),
```

Pass `resume` into `process_vod()`.

---

## Step 3 — LLM Retry (`tenacity`)

Wrap every provider's API call with configurable exponential backoff so
transient rate-limit errors and network blips do not silently drop candidates.

### Dependency

`pyproject.toml` — add to core deps:

```toml
"tenacity>=8.2",
```

### Config addition

`src/clipsmith/config/models.py` — add `RetryConfig`, attach to `LLMConfig`:

```python
class RetryConfig(BaseModel):
    max_attempts: int = 3
    wait_min_s: float = 1.0
    wait_max_s: float = 30.0
    multiplier: float = 2.0
    jitter: bool = True
```

```python
class LLMConfig(BaseModel):
    # existing fields ...
    retry: RetryConfig = RetryConfig()
```

`config.yaml` template addition:

```yaml
llm:
  retry:
    max_attempts: 3
    wait_min_s: 1.0
    wait_max_s: 30.0
    multiplier: 2.0
    jitter: true
```

### `src/clipsmith/llm/base.py` — retry builder

```python
import tenacity
from clipsmith.config.models import RetryConfig

_RETRIED_EXCEPTIONS = (
    # populated dynamically below to avoid hard imports
)

def build_retry(cfg: RetryConfig, log, *, candidate_id: str, provider: str):
    """Return a tenacity Retrying context manager configured from RetryConfig."""
    import anthropic, openai, httpx

    retried = (
        anthropic.RateLimitError,
        anthropic.APIConnectionError,
        openai.RateLimitError,
        openai.APIConnectionError,
        httpx.TimeoutException,
        httpx.ConnectError,
    )

    def _before_sleep(retry_state):
        log.warning(
            "llm_retry",
            attempt=retry_state.attempt_number,
            wait_s=round(retry_state.next_action.sleep, 2),
            error=str(retry_state.outcome.exception()),
            candidate_id=candidate_id,
            provider=provider,
        )

    wait = tenacity.wait_exponential(
        multiplier=cfg.multiplier,
        min=cfg.wait_min_s,
        max=cfg.wait_max_s,
    )
    if cfg.jitter:
        wait = tenacity.wait_combine(wait, tenacity.wait_random(0, 1))

    return tenacity.Retrying(
        retry=tenacity.retry_if_exception_type(retried),
        stop=tenacity.stop_after_attempt(cfg.max_attempts),
        wait=wait,
        before_sleep=_before_sleep,
        reraise=True,
    )
```

### Provider changes

Each provider's `pick()` method wraps its inner API call with `build_retry()`.
Pattern shown for Anthropic; OpenAI and Ollama follow the same shape:

```python
# src/clipsmith/llm/anthropic_provider.py

def pick(self, transcript_window, candidate, stream_context) -> ClipPick | None:
    candidate_id = f"{candidate.t_center:.1f}"
    retry = build_retry(self._retry_cfg, log, candidate_id=candidate_id, provider="anthropic")
    t0 = time.monotonic()
    try:
        for attempt in retry:
            with attempt:
                response = self._client.messages.create(...)
        pick = _parse_response(response)
        log.info("llm_pick", candidate_id=candidate_id, provider="anthropic",
                 include=pick.include, score=pick.score,
                 elapsed_ms=round((time.monotonic() - t0) * 1000))
        return pick
    except Exception as exc:
        log.warning("llm_failed", candidate_id=candidate_id, provider="anthropic",
                    attempts=self._retry_cfg.max_attempts, error=str(exc))
        return None
```

**Exceptions that are NOT retried** (fail immediately on first attempt):

- `anthropic.AuthenticationError`
- `openai.AuthenticationError`
- `pydantic.ValidationError` (malformed LLM response)

These signal a configuration problem that retrying cannot fix.

---

## File Layout (final state after Sprint 3)

```
clipsmith/
├── src/clipsmith/
│   ├── logging.py                  NEW — configure_logging(verbose, json_logs)
│   ├── checkpoints.py              NEW — CheckpointManager, STAGES list
│   ├── pipeline.py                 MODIFIED — structlog context, checkpoint hooks, resume param
│   ├── cli/
│   │   └── run.py                  MODIFIED — --resume flag, --json-logs flag
│   ├── config/
│   │   └── models.py               MODIFIED — RetryConfig, CheckpointConfig added
│   ├── llm/
│   │   ├── base.py                 MODIFIED — build_retry() helper
│   │   ├── anthropic_provider.py   MODIFIED — structlog + tenacity retry
│   │   ├── openai_provider.py      MODIFIED — structlog + tenacity retry
│   │   └── ollama_provider.py      MODIFIED — structlog + tenacity retry
│   ├── selection/
│   │   └── selector.py             MODIFIED — llm_pick event with timing
│   └── api/
│       └── worker.py               MODIFIED — configure_logging(json_logs=True), bind run_id
├── pyproject.toml                  MODIFIED — structlog>=24.1, tenacity>=8.2 in core deps
├── config.yaml                     MODIFIED — llm.retry and pipeline.checkpoint sections
└── docs/dev/
    ├── PLAN.md                     MODIFIED — Sprint 2 done, Sprint 3 active (Step 0)
    ├── sprint1.md                  Unchanged
    ├── sprint2.md                  Unchanged
    └── sprint3.md                  This file
```

---

## Verification Checklist

### Step 0 — Docs
- [ ] `PLAN.md` shows Sprint 2 `✅ Done` and Sprint 3 `🚧 In Progress`
- [ ] `mkdocs build --strict` exits 0

### Step 1 — Structured Logging
- [ ] `clipsmith run <vod_id>` pretty-prints stage events with no visual regression
- [ ] `clipsmith run <vod_id> --json-logs` outputs valid newline-delimited JSON (one object per line)
- [ ] Every JSON line includes `run_id`, `vod_id`, `timestamp`, `level`
- [ ] `stage_start` and `stage_done` events appear for each of the six stages
- [ ] `llm_pick` event emitted per candidate, including `include`, `score`, `elapsed_ms`
- [ ] API worker logs include `run_id` bound on every line (not just task creation)
- [ ] Existing `verbose` flag still controls `DEBUG`-level output

### Step 2 — Checkpoints
- [ ] First run of a VOD creates `.checkpoints/<vod_id>/` directory
- [ ] `transcribe.done`, `select.done`, etc. appear after each stage completes
- [ ] `clipsmith run <vod_id> --resume` skips stages that already have sentinels; `stage_skip` logged
- [ ] Killing the process after `transcribe` and re-running with `--resume` starts from `chat`, not `download`
- [ ] A stage that fails does not leave a `.done` file; next `--resume` retries it
- [ ] `CheckpointManager.clear()` removes all sentinels; subsequent run reruns everything
- [ ] `pipeline.checkpoint.enabled: false` in `config.yaml` disables sentinel writes

### Step 3 — LLM Retry
- [ ] Patching the Anthropic client to raise `RateLimitError` once triggers a retry; `llm_retry` logged with `attempt=1`
- [ ] After `max_attempts` failures, `llm_failed` is logged and the candidate is skipped (no crash)
- [ ] `AuthenticationError` does NOT retry — fails immediately on the first attempt
- [ ] Setting `llm.retry.max_attempts: 1` in `config.yaml` disables retries (single attempt only)
- [ ] `wait_min_s` and `wait_max_s` are respected (observable in `wait_s` field of `llm_retry` log)
- [ ] Ollama provider retries `httpx.TimeoutException` using the same policy
