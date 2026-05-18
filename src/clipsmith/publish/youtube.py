"""YouTube Data API v3 upload helper for Shorts."""

from __future__ import annotations

from pathlib import Path
from typing import Any


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubePublisher:
    def __init__(self, credentials_file: str, token_file: str) -> None:
        self._credentials_file = credentials_file
        self._token_file = Path(token_file)

    def _get_service(self) -> Any:
        try:
            from google.oauth2.credentials import Credentials  # noqa: F401
            from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401
            from googleapiclient.discovery import build  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "YouTube publishing requires: pip install 'clipsmith-ai[publish]'"
            ) from exc

        creds = None
        if self._token_file.exists():
            from google.oauth2.credentials import Credentials

            creds = Credentials.from_authorized_user_file(str(self._token_file), SCOPES)

        if not creds or not creds.valid:
            from google_auth_oauthlib.flow import InstalledAppFlow

            flow = InstalledAppFlow.from_client_secrets_file(self._credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
            self._token_file.write_text(creds.to_json())
            self._token_file.chmod(0o600)

        from googleapiclient.discovery import build

        return build("youtube", "v3", credentials=creds)

    def upload(
        self,
        video_path: Path,
        *,
        title: str,
        description: str = "",
        privacy: str = "private",
        category_id: int = 20,
    ) -> str:
        """Upload a clip as a YouTube Short. Returns the watch URL."""
        from googleapiclient.http import MediaFileUpload

        svc = self._get_service()
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": str(category_id),
                "tags": ["#Shorts"],
            },
            "status": {"privacyStatus": privacy},
        }
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        response = svc.videos().insert(part="snippet,status", body=body, media_body=media).execute()
        return f"https://youtube.com/watch?v={response['id']}"
