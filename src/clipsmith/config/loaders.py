"""Configuration loaders: YAML for behavior, .env / environment for secrets."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import AppConfig


def _env_file_paths() -> list[Path]:
    """Return .env search paths: next to the exe (bundled), then CWD."""
    paths: list[Path] = []
    exe_env = Path(sys.executable).parent / ".env"
    if exe_env.parent != Path(".").resolve():
        paths.append(exe_env)
    paths.append(Path(".env"))
    return paths


class Secrets(BaseSettings):
    """Loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=_env_file_paths(), extra="ignore")

    twitch_client_id: str = ""
    twitch_client_secret: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    azure_subscription_id: str = ""
    # Legacy: only needed when running against manually pre-provisioned storage.
    # Per-run provisioning (clipsmith cloud run) does not require these.
    azure_storage_account: str = ""
    azure_storage_key: str = ""
    docker_hub_username: str = ""
    docker_hub_password: str = ""
    google_service_account_json: str = ""
    google_oauth_client_json: str = ""
    google_drive_folder_id: str = ""


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
    return AppConfig.model_validate(data or {})


def load_secrets() -> Secrets:
    return Secrets()
