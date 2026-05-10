"""Tests for the /runs/{id}/clips and /clips/{id} REST endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from clipsmith.db.models import Clip


def _create_run(client: TestClient, vod_id: str = "v1") -> dict:
    return client.post("/runs", json={"vod_id": vod_id}).json()


def _insert_clip(db: Session, run_id: int, filename: str = "test.mp4") -> Clip:
    clip = Clip(run_id=run_id, filename=filename, title="original", score=0.8)
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


def test_list_clips_empty(client: TestClient) -> None:
    run = _create_run(client)
    r = client.get(f"/runs/{run['id']}/clips")
    assert r.status_code == 200
    assert r.json() == []


def test_list_clips_run_not_found(client: TestClient) -> None:
    r = client.get("/runs/9999/clips")
    assert r.status_code == 404


def test_patch_clip_not_found(client: TestClient) -> None:
    r = client.patch("/clips/9999", json={"title": "test"})
    assert r.status_code == 404


def test_patch_clip_title(client: TestClient, db_session: Session) -> None:
    run = _create_run(client)
    clip = _insert_clip(db_session, run["id"])

    r = client.patch(f"/clips/{clip.id}", json={"title": "updated"})
    assert r.status_code == 200
    assert r.json()["title"] == "updated"


def test_patch_clip_approve(client: TestClient, db_session: Session) -> None:
    run = _create_run(client)
    clip = _insert_clip(db_session, run["id"])

    r = client.patch(f"/clips/{clip.id}", json={"approved": True})
    assert r.status_code == 200
    assert r.json()["approved"] is True


def test_patch_clip_reject(client: TestClient, db_session: Session) -> None:
    run = _create_run(client)
    clip = _insert_clip(db_session, run["id"])

    r = client.patch(f"/clips/{clip.id}", json={"approved": False})
    assert r.status_code == 200
    assert r.json()["approved"] is False


def test_list_clips_returns_inserted(client: TestClient, db_session: Session) -> None:
    run = _create_run(client)
    _insert_clip(db_session, run["id"], filename="clip_01.mp4")
    _insert_clip(db_session, run["id"], filename="clip_02.mp4")

    r = client.get(f"/runs/{run['id']}/clips")
    assert r.status_code == 200
    filenames = {c["filename"] for c in r.json()}
    assert filenames == {"clip_01.mp4", "clip_02.mp4"}
