"""Download Twitch chat replay via chat-downloader and save as JSON."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# Emotes associated with hype/laughter moments (cross-language).
HYPE_EMOTES = frozenset({
    "KEKW", "OMEGALUL", "LUL", "PogChamp", "Pog", "PogO",
    "LULW", "KEKLEO", "xD", "JAJAJA", "monkaS", "GIGACHAD",
    "widepeepoHappy", "Pepega", "OMEGALUL", "EZ",
})


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


def _parse_message(raw: dict) -> ChatMessage | None:
    t = raw.get("time_in_seconds")
    if t is None:
        return None
    msg = raw.get("message", "") or ""
    author = (raw.get("author") or {}).get("name", "") or ""
    is_clip = msg.strip().lower().startswith("!clip")
    tokens = set(msg.split())
    hype = len(tokens & HYPE_EMOTES)
    return ChatMessage(
        time_in_seconds=float(t),
        message=msg,
        author=author,
        is_clip_command=is_clip,
        hype_emote_count=hype,
    )


def download_chat(
    video_id: str,
    work_dir: Path,
    *,
    overwrite: bool = False,
) -> ChatLog:
    """Fetch chat replay for a VOD using chat-downloader.

    Saves chat.json alongside the VOD in work_dir/<video_id>/.
    Returns cached result on subsequent calls unless overwrite=True.
    """
    vod_dir = work_dir / video_id
    vod_dir.mkdir(parents=True, exist_ok=True)
    out_path = vod_dir / "chat.json"

    if out_path.exists() and not overwrite:
        log.info("loading cached chat: %s", out_path)
        return ChatLog.from_json(out_path.read_text(encoding="utf-8"))

    # chat-downloader outputs one JSON object per line (NDJSON).
    url = f"https://www.twitch.tv/videos/{video_id}"
    cmd = ["chat_downloader", url, "--output", str(out_path), "--message_types", "text_message"]
    log.info("running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)

    # chat-downloader writes its own JSON file; parse it.
    return _load_from_file(video_id, out_path)


def _load_from_file(video_id: str, path: Path) -> ChatLog:
    """Parse whatever chat-downloader wrote and normalise to ChatLog."""
    raw_text = path.read_text(encoding="utf-8").strip()

    # chat-downloader can output a JSON array or NDJSON depending on version.
    if raw_text.startswith("["):
        raw_items: list[dict] = json.loads(raw_text)
    else:
        raw_items = [json.loads(line) for line in raw_text.splitlines() if line.strip()]

    messages: list[ChatMessage] = []
    for item in raw_items:
        msg = _parse_message(item)
        if msg is not None:
            messages.append(msg)

    log.info("chat loaded: %d messages for VOD %s", len(messages), video_id)
    chat = ChatLog(video_id=video_id, messages=messages)
    # Overwrite with our normalised format so future loads use from_json fast path.
    path.write_text(chat.to_json(), encoding="utf-8")
    return chat
