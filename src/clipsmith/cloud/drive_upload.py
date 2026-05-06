"""Google Drive upload via OAuth2 user credentials.

Folder structure written to Drive:
    <root>/
        <game_name>/
            <date>/          <- e.g. 2026-04-26
                clip_01_....mp4
                clip_02_....mp4

First-time setup:
    1. In Google Cloud Console, create an OAuth 2.0 Client ID (Desktop app).
    2. Download the JSON and set GOOGLE_OAUTH_CLIENT_JSON in .env.
    3. Run `clipsmith cloud drive-auth` — opens a browser once, saves a token.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..settings import Secrets

log = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_FOLDER_MIME = "application/vnd.google-apps.folder"
_TOKEN_PATH = Path.home() / ".clipsmith_drive_token.json"


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _run_oauth_flow(secrets: Secrets) -> Any:
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not secrets.google_oauth_client_json:
        raise ValueError(
            "GOOGLE_OAUTH_CLIENT_JSON is not set in .env\n"
            "Download an OAuth 2.0 Desktop app client JSON from Google Cloud Console,\n"
            "set GOOGLE_OAUTH_CLIENT_JSON in .env, then run: clipsmith cloud drive-auth"
        )
    client_json = Path(secrets.google_oauth_client_json)
    if not client_json.exists():
        raise FileNotFoundError(f"OAuth client JSON not found: {client_json}")

    flow = InstalledAppFlow.from_client_secrets_file(str(client_json), _SCOPES)
    return flow.run_local_server(port=0)


def _load_or_authorize(secrets: Secrets) -> Any:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = None
    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = _run_oauth_flow(secrets)
        _TOKEN_PATH.write_text(creds.to_json())

    return creds


def authorize_drive(secrets: Secrets) -> None:
    """Run the OAuth browser flow and persist the token. Called from `drive-auth` command."""
    creds = _run_oauth_flow(secrets)
    _TOKEN_PATH.write_text(creds.to_json())
    log.info("Drive credentials saved to %s", _TOKEN_PATH)


def _drive_service_sa(secrets: Secrets) -> Any:
    """Build a Drive service using a service account (fallback; fails on personal Drive quota)."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_path = Path(secrets.google_service_account_json)
    if not sa_path.exists():
        raise FileNotFoundError(
            f"Google service account key not found: {sa_path}\n"
            "Set GOOGLE_SERVICE_ACCOUNT_JSON in .env to the path of your JSON key file."
        )
    creds = service_account.Credentials.from_service_account_file(str(sa_path), scopes=_SCOPES)
    return build("drive", "v3", credentials=creds)


def _drive_service(secrets: Secrets) -> Any:
    from googleapiclient.discovery import build

    if secrets.google_oauth_client_json or _TOKEN_PATH.exists():
        return build("drive", "v3", credentials=_load_or_authorize(secrets))

    if secrets.google_service_account_json:
        log.warning(
            "Service accounts have no Drive storage quota on personal accounts. "
            "Run `clipsmith cloud drive-auth` to set up OAuth credentials instead."
        )
        return _drive_service_sa(secrets)

    raise ValueError(
        "No Google Drive credentials configured.\n"
        "Run `clipsmith cloud drive-auth` or set GOOGLE_OAUTH_CLIENT_JSON in .env."
    )


# ---------------------------------------------------------------------------
# Folder helpers
# ---------------------------------------------------------------------------


def _find_or_create_folder(service: Any, name: str, parent_id: str) -> str:
    """Return the Drive folder ID for `name` under `parent_id`, creating it if absent."""
    escaped = name.replace("'", "\\'")
    query = (
        f"name='{escaped}' and '{parent_id}' in parents"
        f" and mimeType='{_FOLDER_MIME}' and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id)", spaces="drive").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    folder = (
        service.files()
        .create(
            body={"name": name, "mimeType": _FOLDER_MIME, "parents": [parent_id]},
            fields="id",
        )
        .execute()
    )
    log.info("created Drive folder: %s", name)
    return folder["id"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def upload_clips(
    clips: list[Path],
    game_name: str,
    date_str: str,
    secrets: Secrets,
) -> str:
    """Upload clips into <root>/<game_name>/<date_str>/ on Drive.

    Returns the webViewLink of the date subfolder.
    """
    from googleapiclient.http import MediaFileUpload

    if not secrets.google_drive_folder_id:
        raise ValueError("GOOGLE_DRIVE_FOLDER_ID is not set in .env")

    service = _drive_service(secrets)
    root_id = secrets.google_drive_folder_id

    game_folder_id = _find_or_create_folder(service, game_name, root_id)
    date_folder_id = _find_or_create_folder(service, date_str, game_folder_id)

    for clip in clips:
        media = MediaFileUpload(str(clip), mimetype="video/mp4", resumable=True)
        service.files().create(
            body={"name": clip.name, "parents": [date_folder_id]},
            media_body=media,
            fields="id",
        ).execute()
        log.info("uploaded %s", clip.name)

    folder_meta = service.files().get(fileId=date_folder_id, fields="webViewLink").execute()
    link: str = folder_meta["webViewLink"]
    log.info("clips available at %s", link)
    return link
