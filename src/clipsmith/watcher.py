"""Polls Helix for new archive VODs and emits VOD events."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass

from .settings import AppConfig, Secrets
from .state import State
from .twitch_client import TwitchClient, Video

log = logging.getLogger(__name__)


@dataclass
class VodEvent:
    channel: str
    video: Video


def watch(
    config: AppConfig,
    secrets: Secrets,
    *,
    state: State | None = None,
    once: bool = False,
) -> Iterator[VodEvent]:
    """Yield a VodEvent each time a new archive VOD appears for any configured channel.

    Set once=True to do a single pass (useful for tests / one-shot CLI).
    """
    state = state or State()
    with TwitchClient(secrets.twitch_client_id, secrets.twitch_client_secret) as tc:
        # Resolve logins -> user ids once.
        user_ids: dict[str, str] = {}
        for login in config.channels:
            try:
                user_ids[login] = tc.get_user_id(login)
                log.info("resolved %s -> user_id=%s", login, user_ids[login])
            except LookupError:
                log.warning("channel not found: %s", login)

        while True:
            for login, user_id in user_ids.items():
                try:
                    videos = tc.get_videos(user_id, video_type="archive", first=5)
                except Exception as exc:  # transient network / 5xx — keep polling
                    log.warning("get_videos(%s) failed: %s", login, exc)
                    continue
                for v in videos:
                    if v.id in state.seen:
                        continue
                    state.mark_seen(v.id)
                    yield VodEvent(channel=login, video=v)
            if once:
                return
            time.sleep(config.poll_interval_s)
