"""Chat domain models: ChatMessage, ChatLog."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Self

# Emotes associated with hype/laughter moments (cross-language).
HYPE_EMOTES = frozenset(
    {
        "KEKW",
        "OMEGALUL",
        "LUL",
        "PogChamp",
        "Pog",
        "PogO",
        "LULW",
        "KEKLEO",
        "xD",
        "JAJAJA",
        "monkaS",
        "GIGACHAD",
        "widepeepoHappy",
        "Pepega",
        "OMEGALUL",
        "EZ",
    }
)


@dataclass
class ChatMessage:
    time_in_seconds: float
    message: str
    author: str
    is_clip_command: bool  # message starts with !clip
    hype_emote_count: int  # number of HYPE_EMOTES found in message


@dataclass
class ChatLog:
    video_id: str
    messages: list[ChatMessage]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls: type[Self], text: str) -> Self:
        d = json.loads(text)
        d["messages"] = [ChatMessage(**m) for m in d["messages"]]
        return cls(**d)
