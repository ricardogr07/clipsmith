"""Ephemeral per-run Azure resource provisioning and teardown."""

from __future__ import annotations

import logging
import secrets as _secrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..settings import AppConfig, Secrets

log = logging.getLogger(__name__)

_WORK_SHARE = "clipsmith-work"
_OUT_SHARE = "clipsmith-out"


@dataclass
class RunContext:
    resource_group: str
    storage_account: str
    storage_key: str
    location: str


def _unique_storage_name() -> str:
    """Generate a globally unique storage account name (13 chars, lowercase alphanumeric)."""
    return f"clips{_secrets.token_hex(4)}"


def _rg_name(vod_id: str) -> str:
    ts = int(time.time())
    return f"rg-clipsmith-{vod_id[:8]}-{ts}"


def _resource_client(secrets: Secrets) -> Any:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.resource import ResourceManagementClient

    return ResourceManagementClient(DefaultAzureCredential(), secrets.azure_subscription_id)


def _storage_client(secrets: Secrets) -> Any:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.storage import StorageManagementClient

    return StorageManagementClient(DefaultAzureCredential(), secrets.azure_subscription_id)


def provision_run_resources(vod_id: str, config: AppConfig, secrets: Secrets) -> RunContext:
    """Create a fresh resource group, storage account, and file shares for one pipeline run."""
    rg_name = _rg_name(vod_id)
    sa_name = _unique_storage_name()
    location = config.cloud.location

    rc = _resource_client(secrets)
    sc = _storage_client(secrets)

    log.info("creating resource group %s in %s", rg_name, location)
    rc.resource_groups.create_or_update(rg_name, {"location": location})

    log.info("creating storage account %s", sa_name)
    try:
        sc.storage_accounts.begin_create(
            rg_name,
            sa_name,
            {"sku": {"name": "Standard_LRS"}, "kind": "StorageV2", "location": location},
        ).result()
    except Exception as exc:
        if "StorageAccountAlreadyTaken" in str(exc):
            sa_name = _unique_storage_name()
            log.info("name collision — retrying with %s", sa_name)
            sc.storage_accounts.begin_create(
                rg_name,
                sa_name,
                {"sku": {"name": "Standard_LRS"}, "kind": "StorageV2", "location": location},
            ).result()
        else:
            raise

    keys_result = sc.storage_accounts.list_keys(rg_name, sa_name)
    sa_key: str = keys_result.keys[0].value

    for share_name, quota_gb in [(_WORK_SHARE, 50), (_OUT_SHARE, 20)]:
        sc.file_shares.create(rg_name, sa_name, share_name, {"share_quota": quota_gb})
        log.info("created file share %s (%d GB)", share_name, quota_gb)

    return RunContext(
        resource_group=rg_name,
        storage_account=sa_name,
        storage_key=sa_key,
        location=location,
    )


def teardown_run_resources(run_ctx: RunContext, secrets: Secrets) -> None:
    """Delete the resource group — cascades to storage account, file shares, and any ACI group."""
    log.info("deleting resource group %s (cascade delete)", run_ctx.resource_group)
    try:
        rc = _resource_client(secrets)
        rc.resource_groups.begin_delete(run_ctx.resource_group).result()
        log.info("resource group %s deleted", run_ctx.resource_group)
    except Exception as exc:
        log.error("teardown failed for %s: %s", run_ctx.resource_group, exc)
        raise
