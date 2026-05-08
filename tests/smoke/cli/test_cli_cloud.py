"""Smoke tests for the `clipsmith cloud` command group."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from clipsmith.cli import app

runner = CliRunner()


def _azure_mgmt_modules() -> dict:
    """Minimal Azure module stubs for setup command tests."""
    azure = ModuleType("azure")
    identity = ModuleType("azure.identity")
    mgmt = ModuleType("azure.mgmt")
    resource_mod = ModuleType("azure.mgmt.resource")
    storage_mod = ModuleType("azure.mgmt.storage")

    identity.DefaultAzureCredential = MagicMock(name="DefaultAzureCredential")  # type: ignore[attr-defined]
    resource_mod.ResourceManagementClient = MagicMock(name="ResourceManagementClient")  # type: ignore[attr-defined]
    storage_mod.StorageManagementClient = MagicMock(name="StorageManagementClient")  # type: ignore[attr-defined]

    azure.identity = identity  # type: ignore[attr-defined]
    azure.mgmt = mgmt  # type: ignore[attr-defined]
    mgmt.resource = resource_mod  # type: ignore[attr-defined]
    mgmt.storage = storage_mod  # type: ignore[attr-defined]

    return {
        "azure": azure,
        "azure.identity": identity,
        "azure.mgmt": mgmt,
        "azure.mgmt.resource": resource_mod,
        "azure.mgmt.storage": storage_mod,
    }


# ---------------------------------------------------------------------------
# setup command
# ---------------------------------------------------------------------------


def test_cloud_setup_passes_valid_credentials(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("cloud:\n  docker_image: ricardogr007/clipsmith:latest\n")

    mock_rc = MagicMock()
    mock_rc.resource_groups.list.return_value = iter([])
    mods = _azure_mgmt_modules()
    mods["azure.mgmt.resource"].ResourceManagementClient.return_value = mock_rc

    with patch.dict(sys.modules, mods):
        result = runner.invoke(
            app,
            ["cloud", "setup", "--config", str(cfg)],
            env={"AZURE_SUBSCRIPTION_ID": "sub-123"},
        )

    assert result.exit_code == 0, result.output
    assert "Ready" in result.output


def test_cloud_setup_fails_missing_subscription_id(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("")

    result = runner.invoke(
        app,
        ["cloud", "setup", "--config", str(cfg)],
        env={"AZURE_SUBSCRIPTION_ID": ""},
    )

    assert result.exit_code != 0
    assert "AZURE_SUBSCRIPTION_ID" in result.output


def test_cloud_setup_fails_azure_auth_error(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("")

    mock_rc = MagicMock()
    mock_rc.resource_groups.list.side_effect = RuntimeError("auth failed")
    mods = _azure_mgmt_modules()
    mods["azure.mgmt.resource"].ResourceManagementClient.return_value = mock_rc

    with patch.dict(sys.modules, mods):
        result = runner.invoke(
            app,
            ["cloud", "setup", "--config", str(cfg)],
            env={"AZURE_SUBSCRIPTION_ID": "sub-123"},
        )

    assert result.exit_code != 0
    assert "auth failed" in result.output


# ---------------------------------------------------------------------------
# run command
# ---------------------------------------------------------------------------


def test_cloud_run_dry_run(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("cloud:\n  docker_image: ricardogr007/clipsmith:latest\n")

    mock_runner = MagicMock(return_value=[])
    mock_provision = MagicMock()
    mock_teardown = MagicMock()

    with (
        patch("clipsmith.cli.cloud.run_vod_on_aci", mock_runner),
        patch("clipsmith.cli.cloud.provision_run_resources", mock_provision),
        patch("clipsmith.cli.cloud.teardown_run_resources", mock_teardown),
    ):
        result = runner.invoke(
            app,
            ["cloud", "run", "123456", "--game", "FNAF2", "--config", str(cfg), "--dry-run"],
            env={
                "AZURE_SUBSCRIPTION_ID": "sub",
                "ANTHROPIC_API_KEY": "ant",
            },
        )

    assert result.exit_code == 0, result.output
    assert "dry" in result.output.lower()
    mock_runner.assert_called_once()
    assert mock_runner.call_args.kwargs["dry_run"] is True
    # dry_run must NOT provision or tear down
    mock_provision.assert_not_called()
    mock_teardown.assert_not_called()


def test_cloud_run_provisions_and_tears_down(tmp_path: Path) -> None:
    """Successful run: provision called, run called, teardown called."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("cloud:\n  docker_image: ricardogr007/clipsmith:latest\n")

    from clipsmith.cloud.provisioner import RunContext

    fake_ctx = RunContext(
        resource_group="rg-clipsmith-123456-1",
        storage_account="clipsabcd1234",
        storage_key="key==",
        location="eastus",
    )
    mock_provision = MagicMock(return_value=fake_ctx)
    mock_runner = MagicMock(return_value=[])
    mock_teardown = MagicMock()

    with (
        patch("clipsmith.cli.cloud.provision_run_resources", mock_provision),
        patch("clipsmith.cli.cloud.run_vod_on_aci", mock_runner),
        patch("clipsmith.cli.cloud.teardown_run_resources", mock_teardown),
    ):
        result = runner.invoke(
            app,
            ["cloud", "run", "123456", "--game", "FNAF2", "--config", str(cfg)],
            env={"AZURE_SUBSCRIPTION_ID": "sub", "ANTHROPIC_API_KEY": "ant"},
        )

    assert result.exit_code == 0, result.output
    mock_provision.assert_called_once()
    mock_runner.assert_called_once()
    mock_teardown.assert_called_once_with(fake_ctx, mock_teardown.call_args.args[1])


def test_cloud_run_tears_down_on_pipeline_failure(tmp_path: Path) -> None:
    """Even when run_vod_on_aci raises, teardown must still be called."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("cloud:\n  docker_image: ricardogr007/clipsmith:latest\n")

    from clipsmith.cloud.provisioner import RunContext

    fake_ctx = RunContext(
        resource_group="rg-clipsmith-fail",
        storage_account="clipsfailtest",
        storage_key="key==",
        location="eastus",
    )
    mock_provision = MagicMock(return_value=fake_ctx)
    mock_runner = MagicMock(side_effect=RuntimeError("ACI failed"))
    mock_teardown = MagicMock()

    with (
        patch("clipsmith.cli.cloud.provision_run_resources", mock_provision),
        patch("clipsmith.cli.cloud.run_vod_on_aci", mock_runner),
        patch("clipsmith.cli.cloud.teardown_run_resources", mock_teardown),
    ):
        runner.invoke(
            app,
            ["cloud", "run", "123456", "--game", "FNAF2", "--config", str(cfg)],
            env={"AZURE_SUBSCRIPTION_ID": "sub", "ANTHROPIC_API_KEY": "ant"},
        )

    # Typer/CliRunner catches exceptions — exit code will be non-zero
    mock_teardown.assert_called_once()
    assert mock_teardown.call_args.args[0] is fake_ctx


def test_cloud_run_uses_today_as_default_date(tmp_path: Path) -> None:
    import datetime

    cfg = tmp_path / "config.yaml"
    cfg.write_text("cloud:\n  docker_image: ricardogr007/clipsmith:latest\n")

    vod_dir = tmp_path / "123456"
    vod_dir.mkdir()
    fake_clip = vod_dir / "clip_01.mp4"
    fake_clip.write_bytes(b"data")

    from clipsmith.cloud.provisioner import RunContext

    fake_ctx = RunContext("rg-date-test", "clipsdate1234", "key==", "eastus")
    mock_provision = MagicMock(return_value=fake_ctx)
    mock_runner = MagicMock(return_value=[fake_clip])
    mock_uploader = MagicMock(return_value="https://drive.google.com/fake")
    mock_teardown = MagicMock()

    with (
        patch("clipsmith.cli.cloud.provision_run_resources", mock_provision),
        patch("clipsmith.cli.cloud.run_vod_on_aci", mock_runner),
        patch("clipsmith.cli.cloud.upload_clips", mock_uploader),
        patch("clipsmith.cli.cloud.teardown_run_resources", mock_teardown),
    ):
        result = runner.invoke(
            app,
            ["cloud", "run", "123456", "--game", "FNAF2", "--config", str(cfg)],
            env={
                "AZURE_SUBSCRIPTION_ID": "sub",
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
        cfg.write_text("")

        result = runner.invoke(
            app,
            ["cloud", "run", "123456", "--game", "FNAF2", "--config", str(cfg)],
            env={"AZURE_SUBSCRIPTION_ID": "sub"},
        )

    assert result.exit_code != 0
    assert "docker_image" in result.output
