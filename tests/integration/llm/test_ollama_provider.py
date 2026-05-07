"""Integration tests for llm.ollama_provider — ollama mocked via sys.modules."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from clipsmith.llm.ollama_provider import OllamaProvider
from clipsmith.models.candidates import CandidateMoment


def _candidate() -> CandidateMoment:
    return CandidateMoment(t_center=120.0, score=25.0, sources=["chat_density"], reasons=["spike"])


def _ollama_response(payload: dict) -> SimpleNamespace:
    msg = SimpleNamespace(content=json.dumps(payload))
    return SimpleNamespace(message=msg)


def _mock_ollama_module(return_value=None, side_effect=None) -> MagicMock:
    mod = MagicMock()
    if side_effect is not None:
        mod.chat.side_effect = side_effect
    else:
        mod.chat.return_value = return_value
    return mod


_INCLUDE_PAYLOAD = {
    "include": True,
    "start_offset_s": 110.0,
    "end_offset_s": 135.0,
    "title_es": "momento épico",
    "reason": "High chat activity",
}
_EXCLUDE_PAYLOAD = {
    "include": False,
    "start_offset_s": 110.0,
    "end_offset_s": 135.0,
    "title_es": "sin titulo",
    "reason": "Filler content",
}


def test_ollama_pick_include() -> None:
    provider = OllamaProvider(model="llama3.1:8b")
    mock_mod = _mock_ollama_module(return_value=_ollama_response(_INCLUDE_PAYLOAD))
    with patch.dict(sys.modules, {"ollama": mock_mod}):
        result = provider.pick("some transcript", _candidate(), "stream context")
    assert result is not None
    assert result.include is True
    assert result.title_es == "momento épico"


def test_ollama_pick_exclude() -> None:
    provider = OllamaProvider(model="llama3.1:8b")
    mock_mod = _mock_ollama_module(return_value=_ollama_response(_EXCLUDE_PAYLOAD))
    with patch.dict(sys.modules, {"ollama": mock_mod}):
        result = provider.pick("some transcript", _candidate(), "stream context")
    assert result is not None
    assert result.include is False


def test_ollama_pick_import_error() -> None:
    provider = OllamaProvider()
    with patch.dict(sys.modules, {"ollama": None}):  # type: ignore[dict-item]
        with pytest.raises(RuntimeError, match="pip install"):
            provider.pick("transcript", _candidate(), "context")


def test_ollama_pick_network_error() -> None:
    provider = OllamaProvider(model="llama3.1:8b")
    mock_mod = _mock_ollama_module(side_effect=ConnectionError("ollama not running"))
    with patch.dict(sys.modules, {"ollama": mock_mod}):
        result = provider.pick("transcript", _candidate(), "context")
    assert result is None


def test_ollama_pick_malformed_json() -> None:
    provider = OllamaProvider(model="llama3.1:8b")
    bad_resp = SimpleNamespace(message=SimpleNamespace(content="this is not json {{{"))
    mock_mod = _mock_ollama_module(return_value=bad_resp)
    with patch.dict(sys.modules, {"ollama": mock_mod}):
        result = provider.pick("transcript", _candidate(), "context")
    assert result is None
