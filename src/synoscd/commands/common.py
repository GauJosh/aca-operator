"""Common utilities for CLI commands."""

from typing import Optional, Tuple
from synoscd.config import SynoscdConfig
from synoscd.github import GitHubAppClient
from synoscd.aca import ACAClient
from synoscd.reconciler import Reconciler
from synoscd.logger import get_logger

log = get_logger(__name__)


def parse_csv(value: str) -> list[str]:
    """Parse comma-separated values."""
    return [item.strip() for item in value.split(",") if item.strip()]


def build_clients(
    config_path_override: Optional[str] = None,
) -> Tuple[SynoscdConfig, GitHubAppClient, ACAClient, Reconciler]:
    """Build and initialize all client instances."""
    config = SynoscdConfig()
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
        lines.append("  ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)))
    
    return "\n".join(lines)
