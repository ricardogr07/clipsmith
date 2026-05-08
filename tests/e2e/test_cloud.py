"""Cloud e2e smoke tests — provision real Azure resources, verify reachability, tear down.

These tests require:
- AZURE_SUBSCRIPTION_ID set in environment or .env
- DefaultAzureCredential resolvable (e.g. `az login`, or service principal env vars
  AZURE_CLIENT_ID / AZURE_TENANT_ID / AZURE_CLIENT_SECRET)
- pip install -e ".[cloud]"

Each test provisions a fresh resource group + storage account + file shares, runs its
assertions, then destroys the resource group in a finally block.  Provisioning takes
~30–90 s per test (storage account creation), so the full suite runs in roughly 3–6 min.

Run explicitly with:
    pytest tests/e2e/test_cloud.py --run-e2e -v

Or set AZURE_SUBSCRIPTION_ID and pass --run-e2e:
    AZURE_SUBSCRIPTION_ID=<sub> pytest tests/e2e/test_cloud.py --run-e2e -v
"""

from __future__ import annotations

import os

import pytest

from clipsmith.settings import AppConfig, Secrets


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def azure_sub_id() -> str:
    sub = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
    if not sub:
        pytest.skip("AZURE_SUBSCRIPTION_ID not set — skipping cloud e2e tests")
    return sub


@pytest.fixture(scope="module")
def cfg(azure_sub_id: str) -> AppConfig:
    c = AppConfig()
    c.cloud.location = "eastus"
    return c


@pytest.fixture(scope="module")
def secrets(azure_sub_id: str) -> Secrets:
    return Secrets.model_construct(azure_subscription_id=azure_sub_id)


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_cloud_provision_and_teardown(cfg: AppConfig, secrets: Secrets) -> None:
    """Provision a real resource group + storage account + file shares; verify they exist;
    tear down; verify the resource group is gone."""
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.resource import ResourceManagementClient
    from azure.mgmt.storage import StorageManagementClient

    from clipsmith.cloud.provisioner import provision_run_resources, teardown_run_resources

    run_ctx = provision_run_resources("e2esmoketest", cfg, secrets)

    try:
        # RunContext fields must be well-formed
        assert run_ctx.resource_group.startswith("rg-clipsmith-")
        assert run_ctx.storage_account.startswith("clips")
        assert len(run_ctx.storage_key) > 0
        assert run_ctx.location == "eastus"

        cred = DefaultAzureCredential()

        # Resource group must exist and be named correctly
        rc = ResourceManagementClient(cred, secrets.azure_subscription_id)
        rg = rc.resource_groups.get(run_ctx.resource_group)
        assert rg.name == run_ctx.resource_group

        # Storage account must exist under the provisioned resource group
        sc = StorageManagementClient(cred, secrets.azure_subscription_id)
        sa = sc.storage_accounts.get_properties(run_ctx.resource_group, run_ctx.storage_account)
        assert sa.name == run_ctx.storage_account

    finally:
        teardown_run_resources(run_ctx, secrets)

    # After teardown the resource group must no longer exist
    from azure.core.exceptions import ResourceNotFoundError

    rc2 = ResourceManagementClient(DefaultAzureCredential(), secrets.azure_subscription_id)
    with pytest.raises(ResourceNotFoundError):
        rc2.resource_groups.get(run_ctx.resource_group)


def test_cloud_file_share_roundtrip(cfg: AppConfig, secrets: Secrets) -> None:
    """Provision resources; write a file to clipsmith-work; read it back; verify both shares
    are accessible; tear down."""
    from clipsmith.cloud.azure_runner import _share_client
    from clipsmith.cloud.provisioner import provision_run_resources, teardown_run_resources

    run_ctx = provision_run_resources("e2esharetest", cfg, secrets)

    try:
        payload = b"clipsmith cloud smoke test"

        # Write to the work share and read back
        work = _share_client(secrets, "clipsmith-work", run_ctx)
        f = work.get_file_client("smoke_test.txt")
        f.upload_file(payload)
        downloaded = f.download_file().readall()
        assert downloaded == payload, f"roundtrip mismatch: {downloaded!r} != {payload!r}"

        # Confirm the out share is reachable (no exception expected)
        out = _share_client(secrets, "clipsmith-out", run_ctx)
        list(out.list_directories_and_files())

    finally:
        teardown_run_resources(run_ctx, secrets)
