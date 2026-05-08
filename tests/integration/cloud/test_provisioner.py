"""Integration tests for cloud.provisioner — Azure SDK calls are fully mocked."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from clipsmith.settings import AppConfig, Secrets


def _azure_provision_modules() -> dict:
    """Minimal Azure module stubs for provisioner tests."""
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


@pytest.fixture()
def secrets() -> Secrets:
    return Secrets.model_construct(
        azure_subscription_id="sub-123",
        azure_storage_account="",
        azure_storage_key="",
        anthropic_api_key="",
        openai_api_key="",
        twitch_client_id="",
        twitch_client_secret="",
    )


@pytest.fixture()
def config() -> AppConfig:
    cfg = AppConfig()
    cfg.cloud.location = "eastus"
    return cfg


@pytest.fixture()
def mock_rc() -> MagicMock:
    rc = MagicMock()
    rc.resource_groups.create_or_update.return_value = MagicMock()
    rc.resource_groups.begin_delete.return_value = MagicMock()
    return rc


@pytest.fixture()
def mock_sc() -> MagicMock:
    sc = MagicMock()
    mock_key = MagicMock()
    mock_key.value = "base64key=="
    sc.storage_accounts.begin_create.return_value.result.return_value = MagicMock()
    sc.storage_accounts.list_keys.return_value.keys = [mock_key]
    sc.file_shares.create.return_value = MagicMock()
    return sc


def test_provision_creates_rg_sa_shares(
    config: AppConfig, secrets: Secrets, mock_rc: MagicMock, mock_sc: MagicMock
) -> None:
    with (
        patch.dict(sys.modules, _azure_provision_modules()),
        patch("clipsmith.cloud.provisioner._resource_client", return_value=mock_rc),
        patch("clipsmith.cloud.provisioner._storage_client", return_value=mock_sc),
        patch("clipsmith.cloud.provisioner._rg_name", return_value="rg-clipsmith-testvod-1"),
        patch("clipsmith.cloud.provisioner._unique_storage_name", return_value="clips1234abcd"),
    ):
        from clipsmith.cloud.provisioner import provision_run_resources

        provision_run_resources("testvod123", config, secrets)

    mock_rc.resource_groups.create_or_update.assert_called_once_with(
        "rg-clipsmith-testvod-1", {"location": "eastus"}
    )
    mock_sc.storage_accounts.begin_create.assert_called_once()
    assert mock_sc.file_shares.create.call_count == 2
    share_names = {call.args[2] for call in mock_sc.file_shares.create.call_args_list}
    assert share_names == {"clipsmith-work", "clipsmith-out"}


def test_provision_returns_run_context(
    config: AppConfig, secrets: Secrets, mock_rc: MagicMock, mock_sc: MagicMock
) -> None:
    with (
        patch.dict(sys.modules, _azure_provision_modules()),
        patch("clipsmith.cloud.provisioner._resource_client", return_value=mock_rc),
        patch("clipsmith.cloud.provisioner._storage_client", return_value=mock_sc),
        patch("clipsmith.cloud.provisioner._rg_name", return_value="rg-clipsmith-abc-1"),
        patch("clipsmith.cloud.provisioner._unique_storage_name", return_value="clipsdeadbeef"),
    ):
        from clipsmith.cloud.provisioner import provision_run_resources

        ctx = provision_run_resources("abcdefgh", config, secrets)

    assert ctx.resource_group == "rg-clipsmith-abc-1"
    assert ctx.storage_account == "clipsdeadbeef"
    assert ctx.storage_key == "base64key=="
    assert ctx.location == "eastus"


def test_teardown_calls_rg_delete(secrets: Secrets, mock_rc: MagicMock) -> None:
    from clipsmith.cloud.provisioner import RunContext

    run_ctx = RunContext(
        resource_group="rg-clipsmith-xyz-9",
        storage_account="clipsabcd1234",
        storage_key="key==",
        location="eastus",
    )

    with (
        patch.dict(sys.modules, _azure_provision_modules()),
        patch("clipsmith.cloud.provisioner._resource_client", return_value=mock_rc),
    ):
        from clipsmith.cloud.provisioner import teardown_run_resources

        teardown_run_resources(run_ctx, secrets)

    mock_rc.resource_groups.begin_delete.assert_called_once_with("rg-clipsmith-xyz-9")
    mock_rc.resource_groups.begin_delete.return_value.result.assert_called_once()


def test_teardown_reraises_on_failure(secrets: Secrets) -> None:
    from clipsmith.cloud.provisioner import RunContext

    run_ctx = RunContext(
        resource_group="rg-clipsmith-fail",
        storage_account="clips00000000",
        storage_key="key==",
        location="eastus",
    )

    mock_rc = MagicMock()
    mock_rc.resource_groups.begin_delete.side_effect = RuntimeError("Azure unavailable")

    with (
        patch.dict(sys.modules, _azure_provision_modules()),
        patch("clipsmith.cloud.provisioner._resource_client", return_value=mock_rc),
        pytest.raises(RuntimeError, match="Azure unavailable"),
    ):
        from clipsmith.cloud.provisioner import teardown_run_resources

        teardown_run_resources(run_ctx, secrets)


def test_unique_storage_name_format() -> None:
    from clipsmith.cloud.provisioner import _unique_storage_name

    for _ in range(20):
        name = _unique_storage_name()
        assert name.startswith("clips"), f"expected 'clips' prefix: {name}"
        assert 3 <= len(name) <= 24, f"length out of range: {name}"
        assert name.isalnum(), f"non-alphanumeric chars: {name}"
        assert name.islower(), f"uppercase chars: {name}"
