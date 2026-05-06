"""Unit tests for cloud.drive_upload — Google SDK mocked via sys.modules."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from clipsmith.settings import Secrets

# Sentinel: a path that never exists so tests always take the SA fallback in _drive_service.
_NO_TOKEN = Path("/nonexistent/clipsmith_drive_token.json")


def _make_secrets(sa_path: str = "/fake/sa.json", folder_id: str = "root-folder") -> Secrets:
    return Secrets.model_construct(
        google_service_account_json=sa_path,
        google_oauth_client_json="",
        google_drive_folder_id=folder_id,
        twitch_client_id="",
        twitch_client_secret="",
        openai_api_key="",
        anthropic_api_key="",
        azure_subscription_id="",
        azure_storage_account="",
        azure_storage_key="",
        docker_hub_username="",
        docker_hub_password="",
    )


def _google_modules() -> dict:
    """Fake google module hierarchy so tests run without [cloud] extra installed."""
    google = ModuleType("google")
    google_auth = ModuleType("google.auth")  # type: ignore[attr-defined]
    google_auth_transport = ModuleType("google.auth.transport")
    google_auth_transport_requests = ModuleType("google.auth.transport.requests")
    google_auth_transport_requests.Request = MagicMock(name="Request")  # type: ignore[attr-defined]

    google.oauth2 = ModuleType("google.oauth2")  # type: ignore[attr-defined]
    sa_mod = ModuleType("google.oauth2.service_account")
    sa_mod.Credentials = MagicMock(name="SACredentials")  # type: ignore[attr-defined]
    creds_mod = ModuleType("google.oauth2.credentials")
    creds_mod.Credentials = MagicMock(name="OAuthCredentials")  # type: ignore[attr-defined]

    google_auth_oauthlib = ModuleType("google_auth_oauthlib")
    flow_mod = ModuleType("google_auth_oauthlib.flow")
    flow_mod.InstalledAppFlow = MagicMock(name="InstalledAppFlow")  # type: ignore[attr-defined]

    googleapiclient = ModuleType("googleapiclient")
    discovery = ModuleType("googleapiclient.discovery")
    http_mod = ModuleType("googleapiclient.http")
    discovery.build = MagicMock(name="build")  # type: ignore[attr-defined]
    http_mod.MediaFileUpload = MagicMock(name="MediaFileUpload")  # type: ignore[attr-defined]

    google.oauth2.service_account = sa_mod  # type: ignore[attr-defined]
    google.auth = google_auth  # type: ignore[attr-defined]
    google_auth.transport = google_auth_transport
    google_auth_transport.requests = google_auth_transport_requests

    return {
        "google": google,
        "google.auth": google_auth,
        "google.auth.transport": google_auth_transport,
        "google.auth.transport.requests": google_auth_transport_requests,
        "google.oauth2": google.oauth2,
        "google.oauth2.service_account": sa_mod,
        "google.oauth2.credentials": creds_mod,
        "google_auth_oauthlib": google_auth_oauthlib,
        "google_auth_oauthlib.flow": flow_mod,
        "googleapiclient": googleapiclient,
        "googleapiclient.discovery": discovery,
        "googleapiclient.http": http_mod,
    }


def _make_service(game_folder_id="gf-1", date_folder_id="df-1", existing_folders=False):
    """Return a mock Drive service wired for the folder-creation flow."""
    service = MagicMock()

    empty = {"files": []}
    found_game = {"files": [{"id": game_folder_id}]}
    found_date = {"files": [{"id": date_folder_id}]}

    if existing_folders:
        service.files().list().execute.side_effect = [found_game, found_date]
    else:
        service.files().list().execute.side_effect = [empty, empty]
        service.files().create().execute.side_effect = [
            {"id": game_folder_id},  # game folder creation
            {"id": date_folder_id},  # date folder creation
            {"id": "clip-file-id"},  # clip upload (repeated per clip)
        ] + [{"id": f"clip-{i}"} for i in range(10)]  # extra slots for multiple clips

    service.files().get().execute.return_value = {
        "webViewLink": "https://drive.google.com/drive/folders/df-1"
    }
    return service


# ---------------------------------------------------------------------------
# upload_clips — happy path
# ---------------------------------------------------------------------------


def test_upload_clips_creates_folder_hierarchy(tmp_path: Path) -> None:
    clip = tmp_path / "clip_01_test.mp4"
    clip.write_bytes(b"fake-video")

    fake_sa = tmp_path / "sa.json"
    fake_sa.write_text("{}")
    secrets = _make_secrets(sa_path=str(fake_sa))

    mods = _google_modules()
    mock_service = _make_service()
    mods["googleapiclient.discovery"].build.return_value = mock_service

    with (
        patch.dict(sys.modules, mods),
        patch("clipsmith.cloud.drive_upload._TOKEN_PATH", _NO_TOKEN),
    ):
        from clipsmith.cloud.drive_upload import upload_clips

        link = upload_clips([clip], "FNAF2", "2026-04-26", secrets)

    assert link == "https://drive.google.com/drive/folders/df-1"

    # Two list() calls: one for game folder, one for date folder
    assert mock_service.files().list().execute.call_count == 2

    # Two create() calls for folders + one for the clip
    create_calls = mock_service.files().create.call_args_list
    body_args = [
        c.kwargs.get("body") or c.args[0] if c.args else c.kwargs["body"]
        for c in create_calls
        if (c.kwargs.get("body") or (c.args and isinstance(c.args[0], dict)))
    ]
    names = [b["name"] for b in body_args if isinstance(b, dict) and "name" in b]
    assert "FNAF2" in names
    assert "2026-04-26" in names
    assert "clip_01_test.mp4" in names


def test_upload_clips_reuses_existing_folders(tmp_path: Path) -> None:
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"data")
    fake_sa = tmp_path / "sa.json"
    fake_sa.write_text("{}")
    secrets = _make_secrets(sa_path=str(fake_sa))

    mods = _google_modules()
    mock_service = _make_service(existing_folders=True)
    mods["googleapiclient.discovery"].build.return_value = mock_service

    with (
        patch.dict(sys.modules, mods),
        patch("clipsmith.cloud.drive_upload._TOKEN_PATH", _NO_TOKEN),
    ):
        from clipsmith.cloud.drive_upload import upload_clips

        upload_clips([clip], "Hollow Knight: Silksong", "2026-04-26", secrets)

    # Folders found — no folder create() calls, only clip upload
    list_count = mock_service.files().list().execute.call_count
    assert list_count == 2


def test_upload_clips_uploads_multiple_files(tmp_path: Path) -> None:
    clips = []
    for i in range(3):
        c = tmp_path / f"clip_0{i + 1}.mp4"
        c.write_bytes(b"data")
        clips.append(c)
    fake_sa = tmp_path / "sa.json"
    fake_sa.write_text("{}")
    secrets = _make_secrets(sa_path=str(fake_sa))

    mods = _google_modules()
    mock_service = _make_service()
    mods["googleapiclient.discovery"].build.return_value = mock_service

    with (
        patch.dict(sys.modules, mods),
        patch("clipsmith.cloud.drive_upload._TOKEN_PATH", _NO_TOKEN),
    ):
        from clipsmith.cloud.drive_upload import upload_clips

        upload_clips(clips, "FNAF2", "2026-04-26", secrets)

    # MediaFileUpload should be called once per clip
    http_mod = mods["googleapiclient.http"]
    assert http_mod.MediaFileUpload.call_count == 3


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_upload_clips_missing_sa_file(tmp_path: Path) -> None:
    clip = tmp_path / "v.mp4"
    clip.write_bytes(b"x")
    secrets = _make_secrets(sa_path="/nonexistent/sa.json")

    with (
        patch.dict(sys.modules, _google_modules()),
        patch("clipsmith.cloud.drive_upload._TOKEN_PATH", _NO_TOKEN),
    ):
        from clipsmith.cloud.drive_upload import upload_clips

        with pytest.raises(FileNotFoundError, match="service account key not found"):
            upload_clips([clip], "FNAF2", "2026-04-26", secrets)


def test_upload_clips_missing_folder_id(tmp_path: Path) -> None:
    clip = tmp_path / "v.mp4"
    clip.write_bytes(b"x")
    fake_sa = tmp_path / "sa.json"
    fake_sa.write_text("{}")
    secrets = _make_secrets(sa_path=str(fake_sa), folder_id="")

    with (
        patch.dict(sys.modules, _google_modules()),
        patch("clipsmith.cloud.drive_upload._TOKEN_PATH", _NO_TOKEN),
    ):
        from clipsmith.cloud.drive_upload import upload_clips

        with pytest.raises(ValueError, match="GOOGLE_DRIVE_FOLDER_ID"):
            upload_clips([clip], "FNAF2", "2026-04-26", secrets)
