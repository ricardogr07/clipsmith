"""Tests for the `clipsmith cloud` command group."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from clipsmith.cli import app

runner = CliRunner()


def _azure_fileshare_mod(share_names: list[str]) -> dict:
    """Fake azure.storage.fileshare with a stubbed ShareServiceClient."""
    azure = ModuleType("azure")
    core = ModuleType("azure.core")
    core_creds = ModuleType("azure.core.credentials")
    storage = ModuleType("azure.storage")
    fileshare = ModuleType("azure.storage.fileshare")

    core_creds.AzureNamedKeyCredential = MagicMock(name="AzureNamedKeyCredential")  # type: ignore[attr-defined]

    mock_svc = MagicMock()
    mock_svc.list_shares.return_value = [{"name": n} for n in share_names]
    fileshare.ShareServiceClient = MagicMock(return_value=mock_svc)  # type: ignore[attr-defined]

    azure.core = core  # type: ignore[attr-defined]
    core.credentials = core_creds  # type: ignore[attr-defined]
    azure.storage = storage  # type: ignore[attr-defined]
    storage.fileshare = fileshare  # type: ignore[attr-defined]

    return {
        "azure": azure,
        "azure.core": core,
        "azure.core.credentials": core_creds,
        "azure.storage": storage,
        "azure.storage.fileshare": fileshare,
    }


# ---------------------------------------------------------------------------
# cloud setup
# ---------------------------------------------------------------------------


def test_cloud_setup_passes_with_both_shares(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("cloud:\n  docker_image: ricardogr007/clipsmith:latest\n")

    env = tmp_path / ".env"
    env.write_text("AZURE_SUBSCRIPTION_ID=sub\nAZURE_STORAGE_ACCOUNT=acct\nAZURE_STORAGE_KEY=key\n")

    mods = _azure_fileshare_mod(["clipsmith-work", "clipsmith-out"])
    with patch.dict(sys.modules, mods):
        result = runner.invoke(
            app,
            ["cloud", "setup", "--config", str(cfg)],
            env={
                "AZURE_SUBSCRIPTION_ID": "sub",
                "AZURE_STORAGE_ACCOUNT": "acct",
                "AZURE_STORAGE_KEY": "key",
            },
        )

    assert result.exit_code == 0
    assert "Ready" in result.output


def test_cloud_setup_fails_missing_share(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("")

    mods = _azure_fileshare_mod(["clipsmith-work"])  # clipsmith-out missing
    with patch.dict(sys.modules, mods):
        result = runner.invoke(
            app,
            ["cloud", "setup", "--config", str(cfg)],
            env={
                "AZURE_SUBSCRIPTION_ID": "sub",
                "AZURE_STORAGE_ACCOUNT": "acct",
                "AZURE_STORAGE_KEY": "key",
            },
        )

    assert result.exit_code != 0
    assert "clipsmith-out" in result.output


def test_cloud_setup_fails_missing_env(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("")

    mods = _azure_fileshare_mod([])
    with patch.dict(sys.modules, mods):
        result = runner.invoke(
            app,
            ["cloud", "setup", "--config", str(cfg)],
            env={"AZURE_SUBSCRIPTION_ID": "", "AZURE_STORAGE_ACCOUNT": "", "AZURE_STORAGE_KEY": ""},
        )

    assert result.exit_code != 0
    assert "not set" in result.output


# ---------------------------------------------------------------------------
# cloud run --dry-run
# ---------------------------------------------------------------------------


def test_cloud_run_dry_run(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("cloud:\n  docker_image: ricardogr007/clipsmith:latest\n")

    mock_runner = MagicMock(return_value=[])
    mock_uploader = MagicMock()

    with (
        patch("clipsmith.cli.cloud.run_vod_on_aci", mock_runner),
        patch("clipsmith.cli.cloud.upload_clips", mock_uploader),
    ):
        result = runner.invoke(
            app,
            ["cloud", "run", "123456", "--game", "FNAF2", "--config", str(cfg), "--dry-run"],
            env={
                "AZURE_SUBSCRIPTION_ID": "sub",
                "AZURE_STORAGE_ACCOUNT": "acct",
                "AZURE_STORAGE_KEY": "key",
                "ANTHROPIC_API_KEY": "ant",
            },
        )

    assert result.exit_code == 0, result.output
    assert "dry" in result.output.lower()
    mock_runner.assert_called_once()
    assert mock_runner.call_args.args[0] == "123456"
    assert mock_runner.call_args.kwargs["dry_run"] is True
    mock_uploader.assert_not_called()


def test_cloud_run_uses_today_as_default_date(tmp_path: Path) -> None:
    import datetime

    cfg = tmp_path / "config.yaml"
    cfg.write_text("cloud:\n  docker_image: ricardogr007/clipsmith:latest\n")

    # Mirror download_output structure: <tmpdir>/<vod_id>/clip_01.mp4
    # so cloud_run's shutil.rmtree(clips[0].parent.parent) removes tmp_path, not its parent.
    vod_dir = tmp_path / "123456"
    vod_dir.mkdir()
    fake_clip = vod_dir / "clip_01.mp4"
    fake_clip.write_bytes(b"data")

    mock_runner = MagicMock(return_value=[fake_clip])
    mock_uploader = MagicMock(return_value="https://drive.google.com/fake")

    with (
        patch("clipsmith.cli.cloud.run_vod_on_aci", mock_runner),
        patch("clipsmith.cli.cloud.upload_clips", mock_uploader),
    ):
        result = runner.invoke(
            app,
            ["cloud", "run", "123456", "--game", "FNAF2", "--config", str(cfg)],
            env={
                "AZURE_SUBSCRIPTION_ID": "sub",
                "AZURE_STORAGE_ACCOUNT": "acct",
                "AZURE_STORAGE_KEY": "key",
                "ANTHROPIC_API_KEY": "ant",
                "GOOGLE_SERVICE_ACCOUNT_JSON": "/fake/sa.json",
                "GOOGLE_DRIVE_FOLDER_ID": "folder-id",
            },
        )

    assert result.exit_code == 0, result.output
    upload_call = mock_uploader.call_args
    assert upload_call.args[1] == "FNAF2"
    assert upload_call.args[2] == datetime.date.today().isoformat()


def test_cloud_run_requires_docker_image() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        cfg = Path(d) / "config.yaml"
        cfg.write_text("")  # no docker_image

        result = runner.invoke(
            app,
            ["cloud", "run", "123456", "--game", "FNAF2", "--config", str(cfg)],
            env={
                "AZURE_SUBSCRIPTION_ID": "sub",
                "AZURE_STORAGE_ACCOUNT": "acct",
                "AZURE_STORAGE_KEY": "key",
            },
        )

    assert result.exit_code != 0
    assert "docker_image" in result.output
