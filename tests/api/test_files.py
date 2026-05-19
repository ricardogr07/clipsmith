"""Path traversal prevention tests for the file-serving endpoint.

The endpoint validates filename before any filesystem access. Some payloads are
intercepted earlier at the HTTP-routing layer (Starlette resolves `/` and `..`
in URL paths) — those still return 4xx, which is the security property we care
about. The tests below cover both layers.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestFilePathTraversal:
    """GET /runs/{run_id}/clips/file/{filename} must never serve an unsafe path."""

    # These filenames contain characters rejected by the endpoint's own check
    # (files.py line 21) before any filesystem access.
    @pytest.mark.parametrize(
        "bad_filename",
        [
            "clip\\windows\\path.mp4",  # backslash — caught by endpoint check
            "clip..mp4",  # ".." substring — caught by endpoint check
            "clip.txt",  # wrong extension
            "clip.mp4.sh",  # wrong extension
        ],
    )
    def test_endpoint_rejects_bad_filename_with_400(
        self, client: TestClient, bad_filename: str
    ) -> None:
        resp = client.get(f"/runs/1/clips/file/{bad_filename}")
        assert resp.status_code == 400

    # These filenames contain unencoded `/` which Starlette's URL router
    # resolves before the endpoint is reached, returning 404. The file is
    # never served — that's the security guarantee.
    @pytest.mark.parametrize(
        "bad_filename",
        [
            "../secret.mp4",
            "../../etc/passwd",
            "/absolute/path.mp4",
            "clip%2F..%2Fsecret.mp4",  # %2F decoded by Starlette → path split
        ],
    )
    def test_router_rejects_path_separator_filenames(
        self, client: TestClient, bad_filename: str
    ) -> None:
        resp = client.get(f"/runs/1/clips/file/{bad_filename}")
        assert resp.status_code in (400, 404), (
            f"Expected 400 or 404 for '{bad_filename}', got {resp.status_code}"
        )

    def test_valid_filename_not_in_db_returns_404(self, client: TestClient) -> None:
        """A well-formed filename absent from the DB should 404, not 400."""
        resp = client.get("/runs/999/clips/file/clip_01_test.mp4")
        assert resp.status_code == 404
