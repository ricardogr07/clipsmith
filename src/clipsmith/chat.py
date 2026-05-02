"""Download Twitch chat replay via direct GQL and save as JSON."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

# Emotes associated with hype/laughter moments (cross-language).
HYPE_EMOTES = frozenset({
    "KEKW", "OMEGALUL", "LUL", "PogChamp", "Pog", "PogO",
    "LULW", "KEKLEO", "xD", "JAJAJA", "monkaS", "GIGACHAD",
    "widepeepoHappy", "Pepega", "OMEGALUL", "EZ",
})

_GQL_URL = "https://gql.twitch.tv/gql"
_CLIENT_ID = "kd1unb4b3q4t58fwlpcbzcbnm76a8fp"
# Hash for VideoCommentsByOffsetOrCursor — verified working as of 2026-05.
_COMMENTS_HASH = "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"


@dataclass
class ChatMessage:
    time_in_seconds: float
    message: str
    author: str
    is_clip_command: bool        # message starts with !clip
    hype_emote_count: int        # number of HYPE_EMOTES found in message


@dataclass
class ChatLog:
    video_id: str
    messages: list[ChatMessage]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "ChatLog":
        d = json.loads(text)
        d["messages"] = [ChatMessage(**m) for m in d["messages"]]
        return cls(**d)


def download_chat(
    video_id: str,
    work_dir: Path,
    *,
    overwrite: bool = False,
) -> ChatLog:
    """Fetch chat replay for a VOD via Twitch GQL and save as chat.json.

    Returns cached result on subsequent calls unless overwrite=True.
    """
    vod_dir = work_dir / video_id
    vod_dir.mkdir(parents=True, exist_ok=True)
    out_path = vod_dir / "chat.json"

    if out_path.exists() and not overwrite:
        log.info("loading cached chat: %s", out_path)
        return ChatLog.from_json(out_path.read_text(encoding="utf-8"))

    messages = list(_fetch_all_comments(video_id))
    log.info("chat fetched: %d messages for VOD %s", len(messages), video_id)
    chat = ChatLog(video_id=video_id, messages=messages)
    out_path.write_text(chat.to_json(), encoding="utf-8")
    return chat


def _fetch_all_comments(video_id: str) -> list[ChatMessage]:
    """Paginate through VideoCommentsByOffsetOrCursor until hasNextPage=False."""
    messages: list[ChatMessage] = []
    cursor: str | None = None
    page = 0

    with httpx.Client(timeout=30) as client:
        while True:
            variables: dict = {"videoID": video_id}
            if cursor:
                variables["cursor"] = cursor
            else:
                variables["contentOffsetSeconds"] = 0

            payload = [{
                "operationName": "VideoCommentsByOffsetOrCursor",
                "variables": variables,
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": _COMMENTS_HASH,
                    }
                },
            }]

            resp = client.post(_GQL_URL, json=payload, headers={"Client-ID": _CLIENT_ID})
            resp.raise_for_status()
            body = resp.json()

            video = body[0].get("data", {}).get("video") or {}
            comments = video.get("comments") or {}
            edges = comments.get("edges") or []

            for edge in edges:
                cursor = edge.get("cursor")
                node = edge.get("node")
                if not node:
                    continue
                msg = _parse_node(node)
                if msg is not None:
                    messages.append(msg)

            page += 1
            if page % 20 == 0:
                log.info("chat: fetched %d messages so far (page %d)...", len(messages), page)

            if not comments.get("pageInfo", {}).get("hasNextPage"):
                break

    return messages


def _parse_node(node: dict) -> ChatMessage | None:
    t = node.get("contentOffsetSeconds")
    if t is None:
        return None

    commenter = node.get("commenter") or {}
    author = commenter.get("login") or commenter.get("displayName") or ""

    fragments = (node.get("message") or {}).get("fragments") or []
    # Fragments can be plain text or emote references — concatenate text fields.
    msg = "".join(f.get("text") or "" for f in fragments).strip()

    is_clip = msg.lower().startswith("!clip")
    tokens = set(msg.split())
    hype = len(tokens & HYPE_EMOTES)

    return ChatMessage(
        time_in_seconds=float(t),
        message=msg,
        author=author,
        is_clip_command=is_clip,
        hype_emote_count=hype,
    )
