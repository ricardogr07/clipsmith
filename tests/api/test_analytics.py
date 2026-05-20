"""Analytics endpoint and Sprint 5 feature tests.

Covers: prompt_version field on runs, signal_breakdown on clips,
GET /analytics/signals, GET /analytics/prompts, POST /analytics/runs/{id}/calibrate.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.api.conftest import VALID_KEY
from clipsmith.db.models import Clip, Run, RunStatus


def _create_run(db: Session, prompt_version: str = "v1") -> Run:
    run = Run(
        vod_id="testvod", channel="testchan", status=RunStatus.done, prompt_version=prompt_version
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _add_clip(
    db: Session,
    run: Run,
    *,
    approved: bool | None = None,
    breakdown: dict | None = None,
) -> Clip:
    clip = Clip(
        run_id=run.id,
        filename="clip_01_test.mp4",
        title="Test",
        start_s=0.0,
        end_s=20.0,
        score=75.0,
        approved=approved,
        signal_breakdown=breakdown,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


@pytest.mark.integration
class TestPromptVersion:
    """prompt_version is saved on Run and returned in to_dict()."""

    def test_default_prompt_version_is_v1(self, client: TestClient) -> None:
        with patch("clipsmith.api.routes.runs.start_run"):
            resp = client.post(
                "/runs",
                json={"vod_id": "abc123"},
                headers={"X-Api-Key": VALID_KEY},
            )
        assert resp.status_code == 201
        assert resp.json()["prompt_version"] == "v1"

    def test_prompt_version_v2_accepted(self, client: TestClient) -> None:
        with patch("clipsmith.api.routes.runs.start_run"):
            resp = client.post(
                "/runs",
                json={"vod_id": "abc123", "prompt_version": "v2"},
                headers={"X-Api-Key": VALID_KEY},
            )
        assert resp.status_code == 201
        assert resp.json()["prompt_version"] == "v2"

    def test_invalid_prompt_version_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/runs",
            json={"vod_id": "abc123", "prompt_version": "v3"},
            headers={"X-Api-Key": VALID_KEY},
        )
        assert resp.status_code == 422


@pytest.mark.integration
class TestSignalBreakdown:
    """signal_breakdown is returned in clip to_dict()."""

    def test_clip_returns_signal_breakdown(self, client: TestClient, db: Session) -> None:
        run = _create_run(db)
        _add_clip(db, run, breakdown={"chat_density": 37.5, "transcript_hype": 37.5})

        resp = client.get(f"/runs/{run.id}/clips")
        assert resp.status_code == 200
        clips = resp.json()
        assert len(clips) == 1
        bd = clips[0]["signal_breakdown"]
        assert bd is not None
        assert "chat_density" in bd
        assert "transcript_hype" in bd

    def test_clip_with_no_breakdown_returns_null(self, client: TestClient, db: Session) -> None:
        run = _create_run(db)
        _add_clip(db, run, breakdown=None)

        resp = client.get(f"/runs/{run.id}/clips")
        assert resp.status_code == 200
        assert resp.json()[0]["signal_breakdown"] is None


@pytest.mark.integration
class TestAnalyticsSignals:
    """GET /analytics/signals aggregates per-signal stats."""

    def test_empty_returns_empty_list(self, client: TestClient) -> None:
        resp = client.get("/analytics/signals")
        assert resp.status_code == 200
        assert resp.json() == {"signals": []}

    def test_approved_clip_counted(self, client: TestClient, db: Session) -> None:
        run = _create_run(db)
        _add_clip(db, run, approved=True, breakdown={"chat_density": 50.0})
        _add_clip(db, run, approved=False, breakdown={"chat_density": 30.0})

        resp = client.get("/analytics/signals")
        assert resp.status_code == 200
        signals = {s["signal"]: s for s in resp.json()["signals"]}
        assert "chat_density" in signals
        s = signals["chat_density"]
        assert s["clip_count"] == 2
        assert s["approved_count"] == 1
        assert s["approval_rate"] == 0.5


@pytest.mark.integration
class TestAnalyticsPrompts:
    """GET /analytics/prompts compares approval rate by prompt version."""

    def test_empty_returns_empty_list(self, client: TestClient) -> None:
        resp = client.get("/analytics/prompts")
        assert resp.status_code == 200
        assert resp.json() == {"versions": []}

    def test_two_versions_compared(self, client: TestClient, db: Session) -> None:
        run_v1 = _create_run(db, prompt_version="v1")
        _add_clip(db, run_v1, approved=True)
        _add_clip(db, run_v1, approved=False)

        run_v2 = _create_run(db, prompt_version="v2")
        _add_clip(db, run_v2, approved=True)

        resp = client.get("/analytics/prompts")
        assert resp.status_code == 200
        versions = {v["prompt_version"]: v for v in resp.json()["versions"]}
        assert "v1" in versions
        assert "v2" in versions
        assert versions["v1"]["approval_rate"] == 0.5
        assert versions["v2"]["approval_rate"] == 1.0


@pytest.mark.integration
class TestCalibrateEndpoint:
    """POST /analytics/runs/{id}/calibrate returns EMA weight recommendations."""

    def test_404_for_missing_run(self, client: TestClient) -> None:
        resp = client.post("/analytics/runs/9999/calibrate", headers={"X-Api-Key": VALID_KEY})
        assert resp.status_code == 404

    def test_422_with_no_reviewed_clips(self, client: TestClient, db: Session) -> None:
        run = _create_run(db)
        _add_clip(db, run, approved=None, breakdown={"chat_density": 50.0})

        resp = client.post(f"/analytics/runs/{run.id}/calibrate", headers={"X-Api-Key": VALID_KEY})
        assert resp.status_code == 422

    def test_returns_weights_for_reviewed_clips(self, client: TestClient, db: Session) -> None:
        run = _create_run(db)
        _add_clip(db, run, approved=True, breakdown={"chat_density": 50.0, "transcript_hype": 25.0})
        _add_clip(db, run, approved=False, breakdown={"chat_density": 30.0})

        resp = client.post(f"/analytics/runs/{run.id}/calibrate", headers={"X-Api-Key": VALID_KEY})
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run.id
        assert data["alpha"] == 0.3
        weights = {w["signal"]: w for w in data["weights"]}
        assert "chat_density" in weights
        assert "transcript_hype" in weights

        # EMA over [True, False] with alpha=0.3:
        # ema_0 = 1.0, ema_1 = 0.3*0.0 + 0.7*1.0 = 0.7
        # approval_rate = 0.5 — should differ, proving EMA is not a constant
        cd = weights["chat_density"]
        assert cd["approval_rate"] == 0.5
        assert cd["recommended_weight"] == pytest.approx(0.7, abs=0.01)

        # transcript_hype: only one clip (approved=True), EMA == 1.0 == approval_rate
        th = weights["transcript_hype"]
        assert th["approval_rate"] == 1.0
        assert th["recommended_weight"] == pytest.approx(1.0, abs=0.01)

    def test_calibrate_requires_auth(self, client: TestClient, db: Session) -> None:
        run = _create_run(db)
        resp = client.post(f"/analytics/runs/{run.id}/calibrate")
        assert resp.status_code == 401
