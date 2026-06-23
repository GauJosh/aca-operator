# SynosCD CLI
# Command-line interface for synos

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Optional

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import typer
from synoscd.logger import setup_logging, get_logger
from synoscd.reconciler import OperatorLoop
from synoscd.commands.common import build_clients
from synoscd.commands import reconcile, get, status, logs

app = typer.Typer(
    help="SynosCD - GitOps operator for Azure Container Apps",
    no_args_is_help=True,
)
log = get_logger(__name__)

# Add command groups
app.add_typer(reconcile.app, name="reconcile", help="Control reconciliation")
app.add_typer(get.app, name="get", help="View SynosCD and source state (like 'flux get')")
app.add_typer(status.app, name="status", help="Detailed app status")
app.add_typer(logs.app, name="logs", help="Stream logs from apps/operator")


def _deep_diff(desired: Any, live: Any, path: str = "") -> list[dict[str, Any]]:
    """Return a recursive diff between desired and live values."""
    differences: list[dict[str, Any]] = []

    if isinstance(desired, dict) and isinstance(live, dict):
        keys = sorted(set(desired.keys()) | set(live.keys()))
        for key in keys:
            child_path = f"{path}.{key}" if path else key
            differences.extend(_deep_diff(desired.get(key), live.get(key), child_path))
        return differences

    if isinstance(desired, list) and isinstance(live, list):
        if desired != live:
            differences.append({"path": path or "root", "desired": desired, "live": live})
        return differences

    if desired != live:
        differences.append({"path": path or "root", "desired": desired, "live": live})
    return differences


@app.command()
def bootstrap(
    github_app_id: str = typer.Option(..., help="GitHub App ID"),
    github_app_private_key: str = typer.Option(
        ..., help="GitHub App private key (base64 or path)"
    ),
    github_app_installation_id: str = typer.Option(
        ..., help="GitHub App installation ID"
    ),
    github_repo: str = typer.Option(..., help="GitHub repo (owner/name)"),
    azure_subscription_id: str = typer.Option(..., help="Azure subscription ID"),
    azure_resource_group: str = typer.Option(..., help="Azure resource group name"),
    azure_ace: str = typer.Option(..., help="Azure Container App Environment name"),
):
    """Bootstrap SynosCD operator configuration."""
    setup_logging()
    typer.echo("🚀 SynosCD Bootstrap\n")
    
    log.msg(
        "Bootstrap started",
        github_app_id=github_app_id,
        github_repo=github_repo,
        github_app_installation_id=github_app_installation_id,
        azure_resource_group=azure_resource_group,
        azure_ace=azure_ace,
        azure_subscription_id=azure_subscription_id,
        has_private_key=bool(github_app_private_key),
    )
    
    typer.echo("✓ Configuration validated")
    typer.echo(f"  GitHub Repo:     {github_repo}")
    typer.echo(f"  Azure RG:        {azure_resource_group}")
    typer.echo(f"  Azure ACE:       {azure_ace}")
    typer.echo("\nℹ️  Next steps:")
    typer.echo("  1. Set environment variables based on these values")
    typer.echo("  2. Deploy operator: az containerapp create ...")
    typer.echo("  3. Run: synos get summary to verify setup")


@app.command()
def operator(
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
    interval: Optional[int] = typer.Option(None, "--interval", help="Override reconciliation interval (seconds)"),
    log_level: str = typer.Option("info", "--log-level", help="Log level: debug, info, warning, error"),
):
    """Run the SynosCD operator loop (reconciler daemon)."""
    setup_logging(log_level)
    typer.echo("🚀 Starting SynosCD operator\n")
    log.msg("Starting SynosCD operator", log_level=log_level)

    try:
        config_obj, _, _, reconciler = build_clients(config_path)
        
        # Override interval if provided
        interval_seconds = interval or config_obj.reconcile_interval_seconds
        typer.echo(f"⏱️  Reconciliation interval: {interval_seconds}s")
        typer.echo("💚 Operator running (Ctrl+C to stop)\n")
        
        operator_loop = OperatorLoop(
            reconciler,
            interval_seconds=interval_seconds,
            max_concurrent=config_obj.max_concurrent_reconciles,
        )

        asyncio.run(operator_loop.start())
        
    except KeyboardInterrupt as exc:
        typer.echo("\n✋ Operator stopped")
        raise typer.Exit(code=0) from exc
    except Exception as e:
        log.exception("Operator failed", error=str(e))
        typer.echo(f"\n✗ Operator failed: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def sync(
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without applying"),
):
    """Force a reconciliation pass now (one-shot sync)."""
    setup_logging()
    typer.echo("🔄 Forcing reconciliation sync\n")
    log.msg("Forcing reconciliation sync")

    try:
        _, _, _, reconciler = build_clients(config_path)
        
        if dry_run:
            typer.echo("📋 Dry-run mode: showing what would be synced\n")
        
        result = asyncio.run(reconciler.sync_once())
        
        synced_count = len(result.get("synced", []))
        failed_count = len(result.get("failed", []))
        pruned_count = len(result.get("pruned", []))
        
        status_icon = "✓" if not result.get("failed") else "✗"
        typer.echo(f"\n{status_icon} Sync complete")
        typer.echo(f"  Synced: {synced_count}")
        typer.echo(f"  Failed: {failed_count}")
        typer.echo(f"  Pruned: {pruned_count}")
        
        if result.get("failed"):
            typer.echo("\n  Failed apps:")
            for app_name, error in result["failed"].items():
                typer.echo(f"    - {app_name}: {error}")
            raise typer.Exit(code=1)
            
    except Exception as e:
        log.exception("Sync failed", error=str(e))
        typer.echo(f"\n✗ Sync failed: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def diff(
    app_name: Optional[str] = typer.Option(None, "--app", help="Show diff for one app only"),
    output: str = typer.Option("table", "--output", "-o", help="table|json|yaml"),
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
):
    """Show desired vs live state differences for Apps."""
    setup_logging()
    typer.echo("🔎 Calculating diff between desired and live state\n")

    try:
        _, _, aca_client, reconciler = build_clients(config_path)
        desired_state = asyncio.run(reconciler.fetch_desired_state())
        live_apps = asyncio.run(aca_client.list_apps())
        live_map = {item.get("name"): item for item in live_apps if item.get("name")}

        rows: list[dict[str, Any]] = []

        for resource in desired_state.values():
            if resource.kind.value != "App":
                continue

            name = resource.metadata.name
            if app_name and name != app_name:
                continue

            desired_spec = resource.spec.model_dump(by_alias=True, exclude_none=True)
            desired_norm = aca_client._normalize_desired(desired_spec)
            live = live_map.get(name)
            live_norm = aca_client._normalize_live(live) if live else None

            if not live:
                rows.append(
                    {
                        "name": name,
                        "status": "missing",
                        "managed": bool(resource.metadata.labels and resource.metadata.labels.get("synoscd.io/managed") == "true"),
                        "changes": [{"path": "root", "desired": desired_norm, "live": None}],
                    }
                )
                continue

            changes = _deep_diff(desired_norm, live_norm)
            provisioning_state = (live.get("properties", {}).get("provisioningState") or "unknown").lower()
            latest_ready = live.get("properties", {}).get("latestReadyRevisionName")
            status_text = "in-sync"
            if provisioning_state != "succeeded" or not latest_ready:
                status_text = "unhealthy"
            if changes:
                status_text = "drift"

            rows.append(
                {
                    "name": name,
                    "status": status_text,
                    "managed": bool(resource.metadata.labels and resource.metadata.labels.get("synoscd.io/managed") == "true"),
                    "changes": changes,
                }
            )

        if output == "json":
            typer.echo(json.dumps(rows, indent=2, default=str))
            return

        if output == "yaml":
            import yaml

            typer.echo(yaml.dump(rows, default_flow_style=False, sort_keys=False))
            return

        if not rows:
            typer.echo("No App resources found")
            return

        typer.echo("APP        STATUS     MANAGED  CHANGES")
        typer.echo("---------  ---------  -------  -------")
        for row in rows:
            change_count = len(row.get("changes", []))
            typer.echo(
                f"{row['name']:<9}  {row['status']:<9}  {str(row['managed']):<7}  {change_count}"
            )

    except Exception as e:
        log.exception("Diff failed", error=str(e))
        typer.echo(f"\n✗ Diff failed: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def config(
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
):
    """Show current configuration."""
    setup_logging()
    typer.echo("⚙️  SynosCD Configuration\n")
    
    try:
        config_obj, _, _, _ = build_clients(config_path)
        
        typer.echo("GitHub Configuration:")
        typer.echo(f"  App ID:           {config_obj.github_app_id}")
        typer.echo(f"  Repo Owner:       {config_obj.github_repo_owner}")
        typer.echo(f"  Repo Name:        {config_obj.github_repo_name}")
        typer.echo(f"  Config Path:      {config_obj.github_config_path}")
        
        typer.echo("\nAzure Configuration:")
        typer.echo(f"  Subscription ID:  {config_obj.azure_subscription_id[:8]}...")
        typer.echo(f"  Resource Group:   {config_obj.azure_resource_group}")
        typer.echo(f"  ACE Name:         {config_obj.azure_container_app_environment}")
        
        typer.echo("\nReconciliation Settings:")
        typer.echo(f"  Interval:         {config_obj.reconcile_interval_seconds}s")
        typer.echo(f"  Max Concurrent:   {config_obj.max_concurrent_reconciles}")
        typer.echo(f"  Prune Enabled:    {'Yes' if config_obj.prune_enabled else 'No'}")
        typer.echo(f"  Protected Apps:   {config_obj.protected_apps_csv}")
        
    except Exception as e:
        log.exception("Failed to show config", error=str(e))
        raise typer.Exit(code=1)


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
