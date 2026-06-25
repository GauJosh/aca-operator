"""Common utilities for CLI commands."""

import json
import os
import re
import shlex
import subprocess
from typing import Optional, Tuple
from shutil import which
from pydantic import ValidationError
from synoscd.config import SynoscdConfig
from synoscd.github import GitHubAppClient
from synoscd.aca import ACAClient
from synoscd.reconciler import Reconciler
from synoscd.logger import get_logger

log = get_logger(__name__)


class ConfigValidationError(Exception):
    """Raised when required SynosCD configuration is missing."""


def _format_missing_env_message(error: ValidationError) -> str:
    field_to_env = {
        "github_app_id": "SYNOSCD_GITHUB_APP_ID",
        "github_app_private_key": "SYNOSCD_GITHUB_APP_PRIVATE_KEY",
        "github_app_installation_id": "SYNOSCD_GITHUB_APP_INSTALLATION_ID",
        "github_repo_owner": "SYNOSCD_GITHUB_REPO_OWNER",
        "github_repo_name": "SYNOSCD_GITHUB_REPO_NAME",
        "azure_subscription_id": "SYNOSCD_AZURE_SUBSCRIPTION_ID",
        "azure_resource_group": "SYNOSCD_AZURE_RESOURCE_GROUP",
        "azure_container_app_environment": "SYNOSCD_AZURE_CONTAINER_APP_ENVIRONMENT",
    }

    missing_fields = [
        item.get("loc", [None])[0]
        for item in error.errors()
        if item.get("type") == "missing"
    ]
    missing_envs = [field_to_env.get(field, str(field)) for field in missing_fields]

    if not missing_envs:
        return f"Invalid SynosCD configuration: {error}"

    env_list = "\n  - " + "\n  - ".join(sorted(set(missing_envs)))
    return (
        "Missing required SynosCD configuration environment variables:\n"
        f"{env_list}\n\n"
        "Set them, then re-run your command."
    )


def parse_csv(value: str) -> list[str]:
    """Parse comma-separated values."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _to_windows_path(path: str) -> str:
    if os.name != "nt":
        return path

    match = re.match(r"^/([a-zA-Z])/(.+)$", path)
    if not match:
        return path

    drive = match.group(1).upper()
    remainder = match.group(2).replace("/", "\\")
    return f"{drive}:\\{remainder}"


def _resolve_az() -> str:
    candidates = ["az", "az.cmd", "az.exe", "az.bat"]
    for candidate in candidates:
        resolved = which(candidate)
        if resolved:
            return _to_windows_path(resolved)
    return "az"


def _run_command(
    cmd: list[str], capture_output: bool = True
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except FileNotFoundError:
        if os.name != "nt":
            raise

        bash_path = which("bash")
        if not bash_path:
            raise

        rendered = " ".join(shlex.quote(part) for part in cmd)
        return subprocess.run(
            [_to_windows_path(bash_path), "-lc", rendered],
            check=True,
            text=True,
            capture_output=capture_output,
        )


def fetch_operator_env_map(
    resource_group: str, operator_app_name: str = "synoscd-operator"
) -> dict[str, str]:
    """Fetch live environment variables from the operator Container App."""
    az = _resolve_az()
    result = _run_command(
        [
            az,
            "containerapp",
            "show",
            "-g",
            resource_group,
            "-n",
            operator_app_name,
            "--query",
            "properties.template.containers[0].env",
            "-o",
            "json",
        ]
    )
    text = result.stdout.strip()
    if not text:
        return {}

    env_data = json.loads(text)
    if not isinstance(env_data, list):
        return {}

    env_map: dict[str, str] = {}
    for item in env_data:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if name and value is not None:
            env_map[str(name)] = str(value)
    return env_map


def build_clients(
    config_path_override: Optional[str] = None,
) -> Tuple[SynoscdConfig, GitHubAppClient, ACAClient, Reconciler]:
    """Build and initialize all client instances."""
    try:
        config = SynoscdConfig()
    except ValidationError as exc:
        raise ConfigValidationError(_format_missing_env_message(exc)) from exc
    github_client = GitHubAppClient(
        app_id=config.github_app_id,
        private_key=config.github_app_private_key,
        installation_id=config.github_app_installation_id,
        repo_owner=config.github_repo_owner,
        repo_name=config.github_repo_name,
    )
    aca_client = ACAClient(
        subscription_id=config.azure_subscription_id,
        resource_group=config.azure_resource_group,
        environment_name=config.azure_container_app_environment,
        managed_identity_client_id=config.azure_managed_identity_client_id,
    )
    reconciler = Reconciler(
        github_client,
        aca_client,
        config_path=config_path_override or config.github_config_path,
        prune_enabled=config.prune_enabled,
        protected_apps=parse_csv(config.protected_apps_csv),
        suspended_apps=parse_csv(config.suspended_apps_csv),
    )
    return config, github_client, aca_client, reconciler


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Format data as a text table."""
    if not rows:
        return "No results"

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Build table
    lines = []
    header_row = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    lines.append(header_row)
    lines.append("  ".join("-" * w for w in col_widths))

    for row in rows:
        lines.append(
            "  ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
        )

    return "\n".join(lines)
