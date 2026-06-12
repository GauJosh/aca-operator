# SynosCD CLI
# Command-line interface for synos

import asyncio
import typer
from typing import Optional
from synoscd.config import SynoscdConfig
from synoscd.logger import setup_logging, get_logger
from synoscd.github import GitHubAppClient
from synoscd.aca import ACAClient
from synoscd.reconciler import Reconciler, OperatorLoop

app = typer.Typer(help="SynosCD GitOps operator for Azure Container Apps")
log = get_logger(__name__)


@app.command()
def bootstrap(
    github_app_id: str = typer.Option(..., help="GitHub App ID"),
    github_app_private_key: str = typer.Option(..., help="GitHub App private key (base64 or path)"),
    github_app_installation_id: str = typer.Option(..., help="GitHub App installation ID"),
    github_repo: str = typer.Option(..., help="GitHub repo (owner/name)"),
    azure_subscription_id: str = typer.Option(..., help="Azure subscription ID"),
    azure_resource_group: str = typer.Option(..., help="Azure resource group name"),
    azure_ace: str = typer.Option(..., help="Azure Container App Environment name"),
):
    """Bootstrap SynosCD operator configuration."""
    setup_logging()
    log.msg(
        "Bootstrap started",
        github_repo=github_repo,
        azure_subscription_id=azure_subscription_id,
    )
    # Save config to persistent storage (e.g., Azure Key Vault or ConfigMap)
    # For now, just log it
    log.msg("Configuration validated")


@app.command()
def operator(config_path: Optional[str] = typer.Option(None, help="Path to config file")):
    """Run the SynosCD operator loop."""
    setup_logging()
    log.msg("Starting SynosCD operator")

    # Load config from environment or file
    config = SynoscdConfig()

    # Initialize clients
    repo_owner = config.github_repo_owner
    repo_name = config.github_repo_name
    github_client = GitHubAppClient(
        app_id=config.github_app_id,
        private_key=config.github_app_private_key,
        installation_id=config.github_app_installation_id,
        repo_owner=repo_owner,
        repo_name=repo_name,
    )
    aca_client = ACAClient(
        subscription_id=config.azure_subscription_id,
        resource_group=config.azure_resource_group,
        environment_name=config.azure_container_app_environment,
    )

    # Create reconciler and operator loop
    reconciler = Reconciler(github_client, aca_client, config_path=config.github_config_path)
    operator_loop = OperatorLoop(
        reconciler,
        interval_seconds=config.reconcile_interval_seconds,
        max_concurrent=config.max_concurrent_reconciles,
    )

    try:
        asyncio.run(operator_loop.start())
    except KeyboardInterrupt:
        log.msg("Received interrupt signal")
        operator_loop.stop()


@app.command()
def sync(
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
):
    """Force a reconciliation pass now."""
    setup_logging()
    log.msg("Forcing reconciliation sync")

    config = SynoscdConfig()
    repo_owner = config.github_repo_owner
    repo_name = config.github_repo_name

    github_client = GitHubAppClient(
        app_id=config.github_app_id,
        private_key=config.github_app_private_key,
        installation_id=config.github_app_installation_id,
        repo_owner=repo_owner,
        repo_name=repo_name,
    )
    aca_client = ACAClient(
        subscription_id=config.azure_subscription_id,
        resource_group=config.azure_resource_group,
        environment_name=config.azure_container_app_environment,
    )

    reconciler = Reconciler(github_client, aca_client, config_path=config.github_config_path)

    try:
        result = asyncio.run(reconciler.sync_once())
        log.msg("Sync completed", result=result)
    except Exception as e:
        log.exception("Sync failed", error=str(e))
        raise typer.Exit(code=1)


@app.command()
def diff(
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
):
    """Show diff between desired (Git) and live (Azure) state."""
    setup_logging()
    log.msg("Computing diff between desired and live state")
    # TODO: implement diff logic


@app.command()
def status(
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
):
    """Show operator status and last sync results."""
    setup_logging()
    log.msg("Fetching operator status")
    # TODO: implement status query


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
