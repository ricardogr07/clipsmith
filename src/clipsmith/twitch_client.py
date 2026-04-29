"""Minimal Twitch Helix client. App-token only, no user auth."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

HELIX = "https://api.twitch.tv/helix"
OAUTH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"


@dataclass
class Video:
    id: str
    user_id: str
    user_login: str
    title: str
    created_at: str
    published_at: str
    url: str
    duration: str  # e.g. "3h21m4s"
    type: str  # archive | upload | highlight


@dataclass
class Clip:
    id: str
    url: str
    title: str
    creator_name: str
    video_id: str
    vod_offset: int | None  # seconds into source VOD
    duration: float
    view_count: int
    created_at: str


class TwitchClient:
    def __init__(self, client_id: str, client_secret: str, *, timeout: float = 15.0):
        if not client_id or not client_secret:
            raise ValueError("TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET are required")
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._http = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "TwitchClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _ensure_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        r = self._http.post(
            OAUTH_TOKEN_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
            },
        )
        r.raise_for_status()
        body = r.json()
        self._token = body["access_token"]
        self._token_expires_at = time.time() + int(body.get("expires_in", 3600))
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Client-ID": self._client_id,
            "Authorization": f"Bearer {self._ensure_token()}",
        }

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        r = self._http.get(f"{HELIX}{path}", headers=self._headers(), params=params)
        r.raise_for_status()
        return r.json()

    def get_user_id(self, login: str) -> str:
        body = self._get("/users", {"login": login})
        data = body.get("data") or []
        if not data:
            raise LookupError(f"Twitch user not found: {login}")
        return data[0]["id"]

    def get_videos(
        self,
        user_id: str,
        *,
        video_type: str = "archive",
        first: int = 20,
    ) -> list[Video]:
        body = self._get(
            "/videos",
            {"user_id": user_id, "type": video_type, "first": first},
        )
        return [
            Video(
                id=v["id"],
                user_id=v["user_id"],
                user_login=v["user_login"],
                title=v["title"],
                created_at=v["created_at"],
                published_at=v.get("published_at", v["created_at"]),
                url=v["url"],
                duration=v["duration"],
                type=v["type"],
            )
            for v in body.get("data", [])
        ]

    def get_latest_archive(self, user_id: str) -> Video | None:
        videos = self.get_videos(user_id, video_type="archive", first=1)
        return videos[0] if videos else None

    def get_clips(
        self,
        broadcaster_id: str,
        *,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        first: int = 100,
    ) -> list[Clip]:
        """Fetch clips for a broadcaster. Pages through results up to ~1000."""
        params: dict[str, Any] = {"broadcaster_id": broadcaster_id, "first": first}
        if started_at is not None:
            params["started_at"] = _to_rfc3339(started_at)
        if ended_at is not None:
            params["ended_at"] = _to_rfc3339(ended_at)

        out: list[Clip] = []
        cursor: str | None = None
        for _ in range(10):
            if cursor:
                params["after"] = cursor
            body = self._get("/clips", params)
            for c in body.get("data", []):
                out.append(
                    Clip(
                        id=c["id"],
                        url=c["url"],
                        title=c["title"],
                        creator_name=c["creator_name"],
                        video_id=c.get("video_id", ""),
                        vod_offset=c.get("vod_offset"),
                        duration=float(c.get("duration", 0.0)),
                        view_count=int(c.get("view_count", 0)),
                        created_at=c["created_at"],
                    )
                )
            cursor = (body.get("pagination") or {}).get("cursor")
            if not cursor:
                break
        return out

    def get_clips_for_vod(self, broadcaster_id: str, video_id: str) -> list[Clip]:
        return [c for c in self.get_clips(broadcaster_id) if c.video_id == video_id]


def _to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat().replace("+00:00", "Z")
