"""CLI command group: clipsmith cloud <setup|build|run|status>."""

from __future__ import annotations

import datetime
import logging
import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .cloud.azure_runner import run_vod_on_aci
from .cloud.drive_upload import authorize_drive, upload_clips
from .pipeline import _setup_logging
from .settings import load_config, load_secrets

console = Console()
log = logging.getLogger(__name__)

cloud_app = typer.Typer(help="Azure cloud commands: provision, run, and tear down ACI jobs.")


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------


@cloud_app.command()
def setup(
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Verify Azure infra (resource group, storage account, file shares) is ready."""
    _setup_logging(verbose)
    cfg = load_config(config_path)
    secrets = load_secrets()

    if not secrets.azure_subscription_id:
        console.print("[red]AZURE_SUBSCRIPTION_ID not set in .env[/red]")
        raise typer.Exit(1)
    if not secrets.azure_storage_account:
        console.print("[red]AZURE_STORAGE_ACCOUNT not set in .env[/red]")
        raise typer.Exit(1)
    if not secrets.azure_storage_key:
        console.print("[red]AZURE_STORAGE_KEY not set in .env[/red]")
        raise typer.Exit(1)

    try:
        from azure.core.credentials import AzureNamedKeyCredential
        from azure.storage.fileshare import ShareServiceClient
    except ImportError:
        console.print("[red]Azure packages not installed.[/red] Run: pip install '.[cloud]'")
        raise typer.Exit(1)

    cred = AzureNamedKeyCredential(secrets.azure_storage_account, secrets.azure_storage_key)
    svc = ShareServiceClient(
        account_url=f"https://{secrets.azure_storage_account}.file.core.windows.net",
        credential=cred,
    )

    shares = {s["name"] for s in svc.list_shares()}
    missing = {"clipsmith-work", "clipsmith-out"} - shares
    if missing:
        console.print(f"[red]Missing file shares:[/red] {', '.join(sorted(missing))}")
        console.print("Create them in the Azure Portal under your storage account > File shares.")
        raise typer.Exit(1)

    console.print("[green]OK[/green] Azure storage account reachable")
    console.print("[green]OK[/green] File shares: clipsmith-work, clipsmith-out")
    console.print(f"\n[dim]Resource group:[/dim] {cfg.cloud.resource_group}")
    console.print(
        f"[dim]Docker image:[/dim]    {cfg.cloud.docker_image or '(not set in config.yaml)'}"
    )
    console.print(
        "\n[bold]Ready.[/bold] Next: run [cyan]clipsmith cloud build[/cyan] to push the image."
    )


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------


@cloud_app.command()
def build(
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    push: bool = typer.Option(True, "--push/--no-push", help="Push to Docker Hub after build"),
) -> None:
    """Build the Docker image and push it to Docker Hub."""
    cfg = load_config(config_path)
    image = cfg.cloud.docker_image
    if not image:
        console.print("[red]cloud.docker_image is not set in config.yaml[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Building[/cyan] {image} ...")
    result = subprocess.run(  # noqa: S603
        ["docker", "build", "-t", image, "."],  # noqa: S607
        check=False,
    )
    if result.returncode != 0:
        console.print("[red]docker build failed[/red]")
        raise typer.Exit(result.returncode)

    if push:
        console.print(f"[cyan]Pushing[/cyan] {image} ...")
        result = subprocess.run(  # noqa: S603
            ["docker", "push", image],  # noqa: S607
            check=False,
        )
        if result.returncode != 0:
            console.print("[red]docker push failed[/red]")
            raise typer.Exit(result.returncode)

    console.print(f"[green]Done.[/green] Image ready: {image}")


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@cloud_app.command("run")
def cloud_run(
    vod_id: str = typer.Argument(..., help="Twitch VOD ID to process"),
    game: str = typer.Option(..., "--game", "-g", help="Game name (used as Drive subfolder)"),
    date: str = typer.Option(
        "",
        "--date",
        "-d",
        help="Stream date as YYYY-MM-DD (default: today)",
    ),
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print ACI spec; do not provision"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Provision ACI, run the pipeline, upload clips to Drive, tear everything down."""
    _setup_logging(verbose)

    date_str = date or datetime.date.today().isoformat()
    cfg = load_config(config_path)
    secrets = load_secrets()

    if not cfg.cloud.docker_image:
        console.print("[red]cloud.docker_image is not set in config.yaml[/red]")
        raise typer.Exit(1)

    console.print(
        f"[cyan]cloud run[/cyan]  vod={vod_id}  game=[bold]{game}[/bold]  date={date_str}"
        + ("  [yellow][dry-run][/yellow]" if dry_run else "")
    )

    clips = run_vod_on_aci(
        vod_id,
        config_path,
        cfg,
        secrets,
        dry_run=dry_run,
        verbose=verbose,
    )

    if dry_run or not clips:
        console.print("[dim]Dry run complete - no clips uploaded.[/dim]")
        return

    console.print(f"[cyan]Uploading[/cyan] {len(clips)} clip(s) to Google Drive ...")
    if not secrets.google_service_account_json or not secrets.google_drive_folder_id:
        console.print(
            "[yellow]Google Drive credentials not set - skipping upload.[/yellow]\n"
            f"Clips saved locally: {clips[0].parent}"
        )
        return

    link = upload_clips(clips, game, date_str, secrets)
    console.print(f"\n[green]Done.[/green] Clips: {link}")
    shutil.rmtree(clips[0].parent.parent, ignore_errors=True)


# ---------------------------------------------------------------------------
# drive-auth
# ---------------------------------------------------------------------------


@cloud_app.command("drive-auth")
def drive_auth() -> None:
    """One-time Google Drive OAuth2 login — opens a browser, saves a refresh token."""
    secrets = load_secrets()
    if not secrets.google_oauth_client_json:
        console.print(
            "[red]GOOGLE_OAUTH_CLIENT_JSON is not set in .env[/red]\n"
            "1. Go to Google Cloud Console > APIs & Services > Credentials\n"
            "2. Create an OAuth 2.0 Client ID (Desktop app) and download the JSON\n"
            "3. Set GOOGLE_OAUTH_CLIENT_JSON=<path> in .env\n"
            "4. Re-run this command"
        )
        raise typer.Exit(1)
    authorize_drive(secrets)
    token_path = Path.home() / ".clipsmith_drive_token.json"
    console.print(f"[green]OK[/green] Drive credentials saved to {token_path}")
    console.print("You can now run [cyan]clipsmith cloud run[/cyan] without re-authorizing.")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@cloud_app.command()
def status(
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
) -> None:
    """List active clipsmith ACI jobs in the configured resource group."""
    try:
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.containerinstance import ContainerInstanceManagementClient
    except ImportError:
        console.print("[red]Azure packages not installed.[/red] Run: pip install '.[cloud]'")
        raise typer.Exit(1)

    cfg = load_config(config_path)
    secrets = load_secrets()

    client = ContainerInstanceManagementClient(
        DefaultAzureCredential(), secrets.azure_subscription_id
    )
    groups = list(client.container_groups.list_by_resource_group(cfg.cloud.resource_group))
    clipsmith_groups = [g for g in groups if g.name and g.name.startswith("clipsmith-")]

    if not clipsmith_groups:
        console.print("[dim]No active clipsmith jobs.[/dim]")
        return

    table = Table("Group", "State", "Location", "Image")
    for g in clipsmith_groups:
        state = g.instance_view.state if g.instance_view else "Unknown"
        image = g.containers[0].image if g.containers else "?"
        table.add_row(g.name, state, g.location or "", image)
    console.print(table)
