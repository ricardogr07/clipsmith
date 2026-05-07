"""Smoke tests for CLI flags, config overrides, and argument validation."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from clipsmith.cli import app

runner = CliRunner()


def _plain(output: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[mGKHF]", "", output)


def test_root_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = _plain(result.output)
    assert "process" in out
    assert "setup" in out
    assert "run-vod" in out
    assert "clip" in out


def test_process_help_shows_all_flags() -> None:
    result = runner.invoke(app, ["process", "--help"])
    assert result.exit_code == 0
    out = _plain(result.output)
    assert "--captions" in out
    assert "--reframe" in out
    assert "--skip-transcribe" in out
    assert "--provider" in out


def test_process_rejects_missing_file(tmp_path) -> None:
    result = runner.invoke(app, ["process", str(tmp_path / "missing.mp4")])
    assert result.exit_code != 0


def test_process_rejects_non_mp4(tmp_path) -> None:
    f = tmp_path / "video.avi"
    f.write_text("x")
    result = runner.invoke(app, ["process", str(f)])
    assert result.exit_code != 0
    assert ".mp4" in _plain(result.output)


def test_run_vod_help_shows_captions_reframe() -> None:
    result = runner.invoke(app, ["run-vod", "--help"])
    assert result.exit_code == 0
    out = _plain(result.output)
    assert "--captions" in out
    assert "--reframe" in out


def test_clip_help_shows_captions_reframe() -> None:
    result = runner.invoke(app, ["clip", "--help"])
    assert result.exit_code == 0
    out = _plain(result.output)
    assert "--captions" in out
    assert "--reframe" in out


def test_setup_rejects_invalid_provider() -> None:
    result = runner.invoke(app, ["setup", "--provider", "badprovider", "--key", "sk-test"])
    assert result.exit_code != 0
    assert "Unknown provider" in _plain(result.output)


def test_setup_accepts_anthropic_provider(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("sys.executable", str(tmp_path / "clipsmith.exe"))
    result = runner.invoke(app, ["setup", "--provider", "anthropic", "--key", "sk-ant-test"])
    assert "ANTHROPIC_API_KEY" in _plain(result.output)


def test_setup_accepts_openai_provider(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("sys.executable", str(tmp_path / "clipsmith.exe"))
    result = runner.invoke(app, ["setup", "--provider", "openai", "--key", "sk-openai-test"])
    assert "OPENAI_API_KEY" in _plain(result.output)


def test_reframe_help_shows_command() -> None:
    result = runner.invoke(app, ["reframe", "--help"])
    assert result.exit_code == 0
    out = _plain(result.output)
    assert "video-id" in out or "VIDEO_ID" in out
    assert "stacked" in out
