"""API authentication and input validation tests.

Covers: X-Api-Key enforcement on mutating endpoints, vod_id regex validation,
and provider enum validation on POST /runs.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import VALID_KEY


@pytest.mark.integration
class TestApiKeyEnforcement:
    """POST /runs requires X-Api-Key when CLIPSMITH_API_KEY is set."""

    def test_missing_key_returns_401(self, client: TestClient) -> None:
        resp = client.post("/runs", json={"vod_id": "abc123"})
        assert resp.status_code == 401

    def test_wrong_key_returns_401(self, client: TestClient) -> None:
        resp = client.post("/runs", json={"vod_id": "abc123"}, headers={"X-Api-Key": "wrong"})
        assert resp.status_code == 401

    def test_valid_key_accepted(self, client: TestClient) -> None:
        with patch("clipsmith.api.routes.runs.start_run"):
            resp = client.post(
                "/runs",
                json={"vod_id": "abc123"},
                headers={"X-Api-Key": VALID_KEY},
            )
        assert resp.status_code == 201

    def test_read_endpoints_are_open(self, client: TestClient) -> None:
        """GET /runs must not require auth — dashboard reads without a key."""
        resp = client.get("/runs")
        assert resp.status_code == 200


@pytest.mark.integration
class TestVodIdValidation:
    """vod_id must match ^[a-zA-Z0-9_-]{1,64}$."""

    @pytest.mark.parametrize(
        "bad_id",
        [
            "../../../etc/passwd",
            "id with spaces",
            "",
            "a" * 65,
            "id/traversal",
            "id\x00null",
            "id;injection",
        ],
    )
    def test_invalid_vod_id_rejected(self, client: TestClient, bad_id: str) -> None:
        resp = client.post(
            "/runs",
            json={"vod_id": bad_id},
            headers={"X-Api-Key": VALID_KEY},
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize("good_id", ["abc123", "v123456789", "my-vod_id", "A" * 64])
    def test_valid_vod_id_accepted(self, client: TestClient, good_id: str) -> None:
        with patch("clipsmith.api.routes.runs.start_run"):
            resp = client.post(
                "/runs",
                json={"vod_id": good_id},
                headers={"X-Api-Key": VALID_KEY},
            )
        assert resp.status_code == 201


@pytest.mark.integration
class TestProviderValidation:
    """provider must be one of anthropic | openai | ollama | null."""

    @pytest.mark.parametrize("bad_provider", ["gpt", "claude", "../../../bin/sh", ""])
    def test_invalid_provider_rejected(self, client: TestClient, bad_provider: str) -> None:
        resp = client.post(
            "/runs",
            json={"vod_id": "abc123", "provider": bad_provider},
            headers={"X-Api-Key": VALID_KEY},
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize("good_provider", ["anthropic", "openai", "ollama", None])
    def test_valid_provider_accepted(self, client: TestClient, good_provider: str | None) -> None:
        body = {"vod_id": "abc123"}
        if good_provider is not None:
            body["provider"] = good_provider
        with patch("clipsmith.api.routes.runs.start_run"):
            resp = client.post("/runs", json=body, headers={"X-Api-Key": VALID_KEY})
        assert resp.status_code == 201
