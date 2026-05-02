"""Smoke tests for CLI flags, config overrides, and argument validation."""

from __future__ import annotations

from typer.testing import CliRunner

from clipsmith.cli import app

runner = CliRunner()


def test_root_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "process" in result.output
    assert "setup" in result.output
    assert "run-vod" in result.output
    assert "clip" in result.output


def test_process_help_shows_all_flags():
    result = runner.invoke(app, ["process", "--help"])
    assert result.exit_code == 0
    assert "--captions" in result.output
    assert "--reframe" in result.output
    assert "--skip-transcribe" in result.output
    assert "--provider" in result.output


def test_process_rejects_missing_file(tmp_path):
    result = runner.invoke(app, ["process", str(tmp_path / "missing.mp4")])
    assert result.exit_code != 0


def test_process_rejects_non_mp4(tmp_path):
    f = tmp_path / "video.avi"
    f.write_text("x")
    result = runner.invoke(app, ["process", str(f)])
    assert result.exit_code != 0
    assert ".mp4" in result.output


def test_run_vod_help_shows_captions_reframe():
    result = runner.invoke(app, ["run-vod", "--help"])
    assert result.exit_code == 0
    assert "--captions" in result.output
    assert "--reframe" in result.output


def test_clip_help_shows_captions_reframe():
    result = runner.invoke(app, ["clip", "--help"])
    assert result.exit_code == 0
    assert "--captions" in result.output
    assert "--reframe" in result.output


def test_setup_rejects_invalid_provider():
    result = runner.invoke(app, ["setup", "--provider", "badprovider", "--key", "sk-test"])
    assert result.exit_code != 0
    assert "Unknown provider" in result.output


def test_setup_accepts_anthropic_provider(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.executable", str(tmp_path / "clipsmith.exe"))
    result = runner.invoke(app, ["setup", "--provider", "anthropic", "--key", "sk-ant-test"])
    assert "ANTHROPIC_API_KEY" in result.output


def test_setup_accepts_openai_provider(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.executable", str(tmp_path / "clipsmith.exe"))
    result = runner.invoke(app, ["setup", "--provider", "openai", "--key", "sk-openai-test"])
    assert "OPENAI_API_KEY" in result.output
