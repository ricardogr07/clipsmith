"""SSE endpoint: stream pipeline progress events for a run."""

from __future__ import annotations

import json
import time
from typing import Generator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ...db.models import PipelineEvent, Run, RunStatus
from ...db.session import get_session

router = APIRouter(tags=["stream"])

_POLL_INTERVAL = 0.5  # seconds between DB polls
_KEEPALIVE_INTERVAL = 30  # seconds — beat Azure's 4-min TCP idle timeout


@router.get("/runs/{run_id}/progress", summary="Stream pipeline progress (SSE)")
def stream_progress(run_id: int) -> StreamingResponse:
    """Server-Sent Events stream of PipelineEvent rows for the given run.
    Closes automatically when the run reaches done or failed status."""
    db = get_session()
    try:
        run = db.get(Run, run_id)
        if not run:
            raise HTTPException(404, "Run not found")
    finally:
        db.close()

    return StreamingResponse(_event_generator(run_id), media_type="text/event-stream")


def _event_generator(run_id: int) -> Generator[str, None, None]:
    """Poll pipeline_events for new rows, yielding SSE data frames.

    Sends an SSE comment (': heartbeat') every 30 s when idle to prevent
    Azure Load Balancer's 4-minute TCP idle timeout from killing the stream.
    """
    db = get_session()
    try:
        last_id = 0
        last_yield = time.time()
        while True:
            db.expire_all()
            run = db.get(Run, run_id)

            new_events = (
                db.query(PipelineEvent)
                .filter(PipelineEvent.run_id == run_id, PipelineEvent.id > last_id)
                .order_by(PipelineEvent.id)
                .all()
            )
            for ev in new_events:
                last_id = ev.id
                yield f"data: {json.dumps(ev.to_dict())}\n\n"
                last_yield = time.time()

            if run and run.status in (RunStatus.done, RunStatus.failed):
                payload = {"event": "end", "status": run.status.value, "error": run.error}
                yield f"data: {json.dumps(payload)}\n\n"
                break

            if time.time() - last_yield >= _KEEPALIVE_INTERVAL:
                yield ": heartbeat\n\n"
                last_yield = time.time()

            time.sleep(_POLL_INTERVAL)
    finally:
        db.close()
