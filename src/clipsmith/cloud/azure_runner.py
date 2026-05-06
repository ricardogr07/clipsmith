"""ACI lifecycle + Azure File Share upload/download."""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..settings import AppConfig, Secrets

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 30
_WORK_SHARE = "clipsmith-work"
_OUT_SHARE = "clipsmith-out"


def _aci_client(secrets: Secrets) -> Any:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.containerinstance import ContainerInstanceManagementClient

    return ContainerInstanceManagementClient(
        DefaultAzureCredential(), secrets.azure_subscription_id
    )


def _share_client(secrets: Secrets, share_name: str) -> Any:
    from azure.core.credentials import AzureNamedKeyCredential
    from azure.storage.fileshare import ShareClient

    cred = AzureNamedKeyCredential(secrets.azure_storage_account, secrets.azure_storage_key)
    return ShareClient(
        account_url=f"https://{secrets.azure_storage_account}.file.core.windows.net",
        share_name=share_name,
        credential=cred,
    )


def upload_config(config_path: Path, secrets: Secrets) -> None:
    """Upload config.yaml to the root of the work file share."""
    share = _share_client(secrets, _WORK_SHARE)
    file_client = share.get_file_client("config.yaml")
    data = config_path.read_bytes()
    file_client.upload_file(data)
    log.info("uploaded %s to %s", config_path.name, _WORK_SHARE)


def create_container_group(
    vod_id: str,
    config: AppConfig,
    secrets: Secrets,
    *,
    dry_run: bool = False,
) -> str:
    """Create the ACI container group. Returns the group name."""
    group_name = f"clipsmith-{vod_id}"

    if dry_run:
        log.info(
            "DRY RUN — would create ACI group %s (image=%s)", group_name, config.cloud.docker_image
        )
        return group_name

    from azure.mgmt.containerinstance.models import (
        AzureFileVolume,
        Container,
        ContainerGroup,
        ContainerGroupRestartPolicy,
        EnvironmentVariable,
        ImageRegistryCredential,
        OperatingSystemTypes,
        ResourceRequests,
        ResourceRequirements,
        Volume,
        VolumeMount,
    )

    env_vars = [
        EnvironmentVariable(name="ANTHROPIC_API_KEY", secure_value=secrets.anthropic_api_key),
        EnvironmentVariable(name="OPENAI_API_KEY", secure_value=secrets.openai_api_key),
        EnvironmentVariable(name="TWITCH_CLIENT_ID", secure_value=secrets.twitch_client_id),
        EnvironmentVariable(name="TWITCH_CLIENT_SECRET", secure_value=secrets.twitch_client_secret),
    ]

    volumes = [
        Volume(
            name="work",
            azure_file=AzureFileVolume(
                share_name=_WORK_SHARE,
                storage_account_name=secrets.azure_storage_account,
                storage_account_key=secrets.azure_storage_key,
            ),
        ),
        Volume(
            name="out",
            azure_file=AzureFileVolume(
                share_name=_OUT_SHARE,
                storage_account_name=secrets.azure_storage_account,
                storage_account_key=secrets.azure_storage_key,
            ),
        ),
    ]

    resource_requests = ResourceRequests(
        cpu=config.cloud.aci_cpu,
        memory_in_gb=config.cloud.aci_memory_gb,
    )

    if config.cloud.gpu_sku:
        from azure.mgmt.containerinstance.models import GpuResource, GpuSku

        resource_requests.gpu = GpuResource(count=1, sku=GpuSku(config.cloud.gpu_sku))

    container = Container(
        name="clipsmith",
        image=config.cloud.docker_image,
        environment_variables=env_vars,
        resources=ResourceRequirements(requests=resource_requests),
        volume_mounts=[
            VolumeMount(name="work", mount_path="/app/work"),
            VolumeMount(name="out", mount_path="/app/out"),
        ],
        command=["clipsmith", "run-vod", vod_id, "--config", "/app/work/config.yaml", "-v"],
    )

    registry_creds = None
    if secrets.docker_hub_username and secrets.docker_hub_password:
        registry_creds = [
            ImageRegistryCredential(
                server="index.docker.io",
                username=secrets.docker_hub_username,
                password=secrets.docker_hub_password,
            )
        ]

    group = ContainerGroup(
        location=config.cloud.location,
        containers=[container],
        os_type=OperatingSystemTypes.LINUX,
        restart_policy=ContainerGroupRestartPolicy.NEVER,
        volumes=volumes,
        image_registry_credentials=registry_creds,
    )

    client = _aci_client(secrets)
    log.info("creating container group %s ...", group_name)
    client.container_groups.begin_create_or_update(
        config.cloud.resource_group, group_name, group
    ).result()
    log.info("container group %s created", group_name)
    return group_name


def poll_until_done(
    group_name: str,
    config: AppConfig,
    secrets: Secrets,
    *,
    verbose: bool = False,
) -> str:
    """Poll ACI every 30s until the container group finishes. Returns terminal state string."""
    client = _aci_client(secrets)
    last_log_len = 0

    while True:
        grp = client.container_groups.get(config.cloud.resource_group, group_name)
        state = grp.instance_view.state if grp.instance_view else "Unknown"
        log.info("container group %s: %s", group_name, state)

        if verbose:
            try:
                logs = client.containers.list_logs(
                    config.cloud.resource_group, group_name, "clipsmith"
                )
                content = logs.content or ""
                lines = content.splitlines()
                new_lines = lines[last_log_len:]
                if new_lines:
                    print("\n".join(new_lines), flush=True)
                    last_log_len = len(lines)
            except Exception:
                pass

        if state in ("Succeeded", "Failed", "Stopped"):
            return state

        time.sleep(_POLL_INTERVAL_S)


def download_output(vod_id: str, secrets: Secrets) -> list[Path]:
    """Download out/<vod_id>/ from the file share into a temp dir. Returns list of local paths."""
    share = _share_client(secrets, _OUT_SHARE)
    dir_client = share.get_directory_client(vod_id)

    vod_dir = Path(tempfile.mkdtemp()) / vod_id
    vod_dir.mkdir()

    clips: list[Path] = []
    for item in dir_client.list_directories_and_files():
        if item["is_directory"]:
            continue
        fname: str = item["name"]
        dest = vod_dir / fname
        dest.write_bytes(dir_client.get_file_client(fname).download_file().readall())
        clips.append(dest)
        log.info("downloaded %s", fname)

    log.info("downloaded %d clips to %s", len(clips), vod_dir)
    return clips


def delete_container_group(group_name: str, config: AppConfig, secrets: Secrets) -> None:
    """Delete the ACI container group (stops billing immediately)."""
    client = _aci_client(secrets)
    client.container_groups.begin_delete(config.cloud.resource_group, group_name).result()
    log.info("deleted container group %s", group_name)


def cleanup_file_share(vod_id: str, secrets: Secrets) -> None:
    """Delete <vod_id>/ from both file shares. Errors are logged, not raised."""
    for share_name in (_WORK_SHARE, _OUT_SHARE):
        share = _share_client(secrets, share_name)
        try:
            dir_client = share.get_directory_client(vod_id)
            for item in dir_client.list_directories_and_files():
                if not item["is_directory"]:
                    dir_client.get_file_client(item["name"]).delete_file()
            dir_client.delete_directory()
            log.info("cleaned up %s/%s", share_name, vod_id)
        except Exception as exc:
            log.warning("cleanup failed for %s/%s: %s", share_name, vod_id, exc)


def run_vod_on_aci(
    vod_id: str,
    config_path: Path,
    config: AppConfig,
    secrets: Secrets,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> list[Path]:
    """Full ACI lifecycle: upload config → provision → poll → download → teardown.

    Returns list of downloaded clip paths (empty list on dry_run).
    """
    upload_config(config_path, secrets)
    group_name = create_container_group(vod_id, config, secrets, dry_run=dry_run)

    if dry_run:
        log.info("DRY RUN complete — no ACI resources created")
        return []

    try:
        state = poll_until_done(group_name, config, secrets, verbose=verbose)
        if state != "Succeeded":
            raise RuntimeError(f"Container job finished with state '{state}' — check ACI logs")
        return download_output(vod_id, secrets)
    finally:
        try:
            delete_container_group(group_name, config, secrets)
        except Exception as exc:
            log.warning("could not delete container group %s: %s", group_name, exc)
        cleanup_file_share(vod_id, secrets)
