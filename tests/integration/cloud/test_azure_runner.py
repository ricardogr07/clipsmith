"""Integration tests for cloud.azure_runner — Azure SDK calls are mocked."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from clipsmith.settings import AppConfig, CloudConfig, Secrets


def _azure_sys_modules() -> dict:
    azure = ModuleType("azure")
    core = ModuleType("azure.core")
    core_creds = ModuleType("azure.core.credentials")
    mgmt = ModuleType("azure.mgmt")
    aci = ModuleType("azure.mgmt.containerinstance")
    models = ModuleType("azure.mgmt.containerinstance.models")
    storage = ModuleType("azure.storage")
    fileshare = ModuleType("azure.storage.fileshare")
    identity = ModuleType("azure.identity")

    for cls in [
        "AzureFileVolume",
        "Container",
        "ContainerGroup",
        "ContainerGroupRestartPolicy",
        "EnvironmentVariable",
        "ImageRegistryCredential",
        "OperatingSystemTypes",
        "ResourceRequests",
        "ResourceRequirements",
        "Volume",
        "VolumeMount",
        "GpuResource",
        "GpuSku",
    ]:
        setattr(models, cls, MagicMock(name=cls))

    core_creds.AzureNamedKeyCredential = MagicMock(name="AzureNamedKeyCredential")
    fileshare.ShareClient = MagicMock(name="ShareClient")
    identity.DefaultAzureCredential = MagicMock(name="DefaultAzureCredential")
    aci.ContainerInstanceManagementClient = MagicMock(name="ContainerInstanceManagementClient")

    azure.core = core  # type: ignore[attr-defined]
    core.credentials = core_creds  # type: ignore[attr-defined]
    azure.mgmt = mgmt  # type: ignore[attr-defined]
    mgmt.containerinstance = aci  # type: ignore[attr-defined]
    aci.models = models  # type: ignore[attr-defined]
    azure.storage = storage  # type: ignore[attr-defined]
    storage.fileshare = fileshare  # type: ignore[attr-defined]

    return {
        "azure": azure,
        "azure.core": core,
        "azure.core.credentials": core_creds,
        "azure.mgmt": mgmt,
        "azure.mgmt.containerinstance": aci,
        "azure.mgmt.containerinstance.models": models,
        "azure.storage": storage,
        "azure.storage.fileshare": fileshare,
        "azure.identity": identity,
    }


@pytest.fixture()
def config() -> AppConfig:
    cfg = AppConfig()
    cfg.cloud = CloudConfig(
        resource_group="clipsmith-rg",
        location="eastus",
        storage_account="testaccount",
        docker_image="ricardogr007/clipsmith:latest",
        aci_cpu=4.0,
        aci_memory_gb=16.0,
    )
    return cfg


@pytest.fixture()
def secrets() -> Secrets:
    return Secrets.model_construct(
        azure_subscription_id="sub-123",
        azure_storage_account="testaccount",
        azure_storage_key="key==",
        anthropic_api_key="ant-key",
        openai_api_key="",
        twitch_client_id="",
        twitch_client_secret="",
        google_service_account_json="",
        google_drive_folder_id="",
    )


def test_upload_config(tmp_path: Path, secrets: Secrets) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("channels: []\n")

    mock_file_client = MagicMock()
    mock_share = MagicMock()
    mock_share.get_file_client.return_value = mock_file_client

    with patch("clipsmith.cloud.azure_runner._share_client", return_value=mock_share):
        from clipsmith.cloud.azure_runner import upload_config

        upload_config(cfg_file, secrets)

    mock_share.get_file_client.assert_called_once_with("config.yaml")
    mock_file_client.upload_file.assert_called_once_with(cfg_file.read_bytes())


def test_create_container_group_dry_run(config: AppConfig, secrets: Secrets) -> None:
    from clipsmith.cloud.azure_runner import create_container_group

    with patch("clipsmith.cloud.azure_runner._aci_client") as mock_aci:
        name = create_container_group("123456", config, secrets, dry_run=True)

    assert name == "clipsmith-123456"
    mock_aci.assert_not_called()


def test_create_container_group_live(config: AppConfig, secrets: Secrets) -> None:
    mock_client = MagicMock()
    mock_poller = MagicMock()
    mock_client.container_groups.begin_create_or_update.return_value = mock_poller

    with (
        patch.dict(sys.modules, _azure_sys_modules()),
        patch("clipsmith.cloud.azure_runner._aci_client", return_value=mock_client),
    ):
        from clipsmith.cloud.azure_runner import create_container_group

        name = create_container_group("123456", config, secrets)

    assert name == "clipsmith-123456"
    mock_client.container_groups.begin_create_or_update.assert_called_once()
    call_args = mock_client.container_groups.begin_create_or_update.call_args
    assert call_args.args[0] == "clipsmith-rg"
    assert call_args.args[1] == "clipsmith-123456"
    mock_poller.result.assert_called_once()


def test_poll_until_done_succeeds(config: AppConfig, secrets: Secrets) -> None:
    mock_client = MagicMock()
    mock_grp = MagicMock()
    mock_grp.instance_view.state = "Succeeded"
    mock_client.container_groups.get.return_value = mock_grp

    with (
        patch("clipsmith.cloud.azure_runner._aci_client", return_value=mock_client),
        patch("clipsmith.cloud.azure_runner.time.sleep"),
    ):
        from clipsmith.cloud.azure_runner import poll_until_done

        state = poll_until_done("clipsmith-123456", config, secrets)

    assert state == "Succeeded"
    mock_client.container_groups.get.assert_called_once_with("clipsmith-rg", "clipsmith-123456")


def test_poll_until_done_polls_multiple_times(config: AppConfig, secrets: Secrets) -> None:
    mock_client = MagicMock()
    running = MagicMock()
    running.instance_view.state = "Running"
    done = MagicMock()
    done.instance_view.state = "Succeeded"
    mock_client.container_groups.get.side_effect = [running, running, done]

    with (
        patch("clipsmith.cloud.azure_runner._aci_client", return_value=mock_client),
        patch("clipsmith.cloud.azure_runner.time.sleep"),
    ):
        from clipsmith.cloud.azure_runner import poll_until_done

        state = poll_until_done("clipsmith-123456", config, secrets)

    assert state == "Succeeded"
    assert mock_client.container_groups.get.call_count == 3


def test_download_output_returns_clip_paths(tmp_path: Path, secrets: Secrets) -> None:
    mock_item = {"name": "clip_01_test.mp4", "is_directory": False}
    mock_dir_client = MagicMock()
    mock_dir_client.list_directories_and_files.return_value = [mock_item]
    mock_dir_client.get_file_client.return_value.download_file.return_value.readall.return_value = (
        b"fake-video-data"
    )
    mock_share = MagicMock()
    mock_share.get_directory_client.return_value = mock_dir_client

    with (
        patch("clipsmith.cloud.azure_runner._share_client", return_value=mock_share),
        patch("clipsmith.cloud.azure_runner.tempfile.mkdtemp", return_value=str(tmp_path)),
    ):
        from clipsmith.cloud.azure_runner import download_output

        clips = download_output("123456", secrets)

    assert len(clips) == 1
    assert clips[0].name == "clip_01_test.mp4"
    assert clips[0].read_bytes() == b"fake-video-data"


def test_delete_container_group(config: AppConfig, secrets: Secrets) -> None:
    mock_client = MagicMock()
    mock_poller = MagicMock()
    mock_client.container_groups.begin_delete.return_value = mock_poller

    with patch("clipsmith.cloud.azure_runner._aci_client", return_value=mock_client):
        from clipsmith.cloud.azure_runner import delete_container_group

        delete_container_group("clipsmith-123456", config, secrets)

    mock_client.container_groups.begin_delete.assert_called_once_with(
        "clipsmith-rg", "clipsmith-123456"
    )
    mock_poller.result.assert_called_once()


def test_run_vod_on_aci_dry_run(tmp_path: Path, config: AppConfig, secrets: Secrets) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("channels: []\n")

    mock_share = MagicMock()
    mock_share.get_file_client.return_value = MagicMock()

    with (
        patch("clipsmith.cloud.azure_runner._share_client", return_value=mock_share),
        patch("clipsmith.cloud.azure_runner._aci_client") as mock_aci,
    ):
        from clipsmith.cloud.azure_runner import run_vod_on_aci

        result = run_vod_on_aci("123456", cfg_file, config, secrets, dry_run=True)

    assert result == []
    mock_aci.assert_not_called()
