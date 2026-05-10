"""Tests for the /runs REST endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from starlette.testclient import TestClient


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_runs_empty(client: TestClient) -> None:
    r = client.get("/runs")
    assert r.status_code == 200
    assert r.json() == []


def test_create_run(client: TestClient) -> None:
    r = client.post("/runs", json={"vod_id": "abc123"})
    assert r.status_code == 201
    data = r.json()
    assert data["vod_id"] == "abc123"
    assert data["status"] == "pending"
    assert "id" in data


def test_create_run_with_channel(client: TestClient) -> None:
    r = client.post("/runs", json={"vod_id": "abc123", "channel": "mychannel"})
    assert r.status_code == 201
    assert r.json()["channel"] == "mychannel"


def test_create_run_missing_vod_id(client: TestClient) -> None:
    r = client.post("/runs", json={})
    assert r.status_code == 422


def test_get_run(client: TestClient) -> None:
    created = client.post("/runs", json={"vod_id": "xyz"}).json()
    r = client.get(f"/runs/{created['id']}")
    assert r.status_code == 200
    assert r.json()["vod_id"] == "xyz"


def test_get_run_not_found(client: TestClient) -> None:
    r = client.get("/runs/9999")
    assert r.status_code == 404


def test_list_runs_returns_created(client: TestClient) -> None:
    client.post("/runs", json={"vod_id": "v1"})
    client.post("/runs", json={"vod_id": "v2"})
    r = client.get("/runs")
    assert r.status_code == 200
    vod_ids = {run["vod_id"] for run in r.json()}
    assert {"v1", "v2"} <= vod_ids


def test_api_key_rejects_when_configured(client: TestClient) -> None:
    mock_secrets = MagicMock()
    mock_secrets.clipsmith_api_key = "secret"
    with patch("clipsmith.api.deps._secrets", return_value=mock_secrets):
        r = client.post("/runs", json={"vod_id": "test"})
    assert r.status_code == 401
