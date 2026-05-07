"""Twitch domain models: Video, Clip."""

from __future__ import annotations

from dataclasses import dataclass


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
