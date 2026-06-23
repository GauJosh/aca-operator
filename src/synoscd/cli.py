# SynosCD CLI
# Command-line interface for synos

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from shutil import which
from typing import Any, Optional

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import typer
from synoscd.logger import setup_logging, get_logger
from synoscd.reconciler import OperatorLoop
from synoscd.commands.common import build_clients, parse_csv, ConfigValidationError
from synoscd.commands import reconcile, get, status, logs

app = typer.Typer(
    help="SynosCD - GitOps operator for Azure Container Apps",
    no_args_is_help=True,
)
log = get_logger(__name__)

OPERATOR_ENV_KEYS = {
    "interval": "SYNOSCD_RECONCILE_INTERVAL_SECONDS",
    "prune": "SYNOSCD_PRUNE_ENABLED",
    "protected_apps": "SYNOSCD_PROTECTED_APPS_CSV",
    "max_concurrent": "SYNOSCD_MAX_CONCURRENT_RECONCILES",
    "suspended_apps": "SYNOSCD_SUSPENDED_APPS_CSV",
}

# Add command groups
app.add_typer(reconcile.app, name="reconcile", help="Control reconciliation")
app.add_typer(get.app, name="get", help="View SynosCD and source state (like 'flux get')")
app.add_typer(status.app, name="status", help="Detailed app status")
app.add_typer(logs.app, name="logs", help="Stream logs from apps/operator")


@app.callback()
def _global_options(
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="Increase log verbosity (use -v for info, -vv for debug)",
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
) -> None:
    """Global CLI options."""
    if debug or verbose >= 2:
        level = "DEBUG"
    elif verbose == 1:
        level = "INFO"
    else:
        level = "WARNING"

    os.environ["SYNOSCD_LOG_LEVEL"] = level


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


def _run_command(cmd: list[str], capture_output: bool = True) -> subprocess.CompletedProcess:
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


def _run_tsv(cmd: list[str]) -> str:
    return _run_command(cmd).stdout.strip()


def _run_json(cmd: list[str]) -> Any:
    text = _run_command(cmd).stdout.strip()
    if not text:
        return {}
    return json.loads(text)


def _detect_operator_rg(operator_app_name: str, rg_hint: Optional[str]) -> str:
    if rg_hint:
        return rg_hint

    az = _resolve_az()
    rg = _run_tsv(
        [
            az,
            "resource",
            "list",
            "--resource-type",
            "Microsoft.App/containerApps",
            "--name",
            operator_app_name,
            "--query",
            "[0].resourceGroup",
            "-o",
            "tsv",
        ]
    )
    if rg:
        return rg
    raise RuntimeError(
        f"Could not detect resource group for operator '{operator_app_name}'. Use --resource-group."
    )


def _fetch_operator_env_map(resource_group: str, operator_app_name: str) -> dict[str, str]:
    az = _resolve_az()
    env_data = _run_json(
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


def _apply_operator_env_updates(
    resource_group: str,
    operator_app_name: str,
    updates: dict[str, str],
) -> None:
    if not updates:
        return

    az = _resolve_az()
    cmd = [
        az,
        "containerapp",
        "update",
        "-g",
        resource_group,
        "-n",
        operator_app_name,
        "--set-env-vars",
    ]
    cmd.extend([f"{key}={value}" for key, value in updates.items()])
    _run_command(cmd, capture_output=False)


def _print_operator_settings(env_map: dict[str, str]) -> None:
    interval = env_map.get(OPERATOR_ENV_KEYS["interval"], "30")
    prune = env_map.get(OPERATOR_ENV_KEYS["prune"], "false")
    protected = env_map.get(OPERATOR_ENV_KEYS["protected_apps"], "synoscd-operator")
    max_concurrent = env_map.get(OPERATOR_ENV_KEYS["max_concurrent"], "3")
    suspended = env_map.get(OPERATOR_ENV_KEYS["suspended_apps"], "")

    typer.echo("⚙️  Operator Runtime Settings")
    typer.echo(f"  Interval:         {interval}s")
    typer.echo(f"  Prune Enabled:    {'Yes' if prune.lower() == 'true' else 'No'}")
    typer.echo(f"  Max Concurrent:   {max_concurrent}")
    typer.echo(f"  Protected Apps:   {protected or '-'}")
    typer.echo(f"  Suspended Apps:   {suspended or '-'}")


@app.command(
        help="""Bootstrap SynosCD operator configuration.

Examples:
    synos bootstrap --github-app-id 123 --github-app-private-key ./key.pem --github-app-installation-id 456 \
        --github-repo GauJosh/my-aca-config --azure-subscription-id <sub> --azure-resource-group synoscd-dev --azure-ace synoscd-ace
""",
)
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
    """Bootstrap SynosCD operator configuration.

    Examples:
      synos bootstrap --github-app-id 123 --github-app-private-key ./key.pem --github-app-installation-id 456 \
        --github-repo GauJosh/my-aca-config --azure-subscription-id <sub> --azure-resource-group synoscd-dev --azure-ace synoscd-ace
    """
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


@app.command(
        help="""Run the SynosCD operator loop (reconciler daemon).

    Examples:
        synos operator
        synos operator --interval 120
        synos operator --log-level debug
""",
)
def operator(
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
    interval: Optional[int] = typer.Option(None, "--interval", help="Override reconciliation interval (seconds)"),
    log_level: Optional[str] = typer.Option(None, "--log-level", help="Log level: debug, info, warning, error"),
):
    setup_logging(log_level)
    typer.echo("🚀 Starting SynosCD operator\n")
    log.msg("Starting SynosCD operator", log_level=(log_level or os.getenv("SYNOSCD_LOG_LEVEL", "WARNING")))

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
    except ConfigValidationError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)
    except Exception as e:
        log.exception("Operator failed", error=str(e))
        typer.echo(f"\n✗ Operator failed: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(
        help="""Force a reconciliation pass now (one-shot sync).

Examples:
    synos sync
    synos sync --dry-run
""",
)
def sync(
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without applying"),
):
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
            
    except ConfigValidationError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)
    except Exception as e:
        log.exception("Sync failed", error=str(e))
        typer.echo(f"\n✗ Sync failed: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(
        help="""Show desired vs live state differences for Apps.

Examples:
    synos diff
    synos diff --app demo-app
    synos diff -o yaml
""",
)
def diff(
    app_name: Optional[str] = typer.Option(None, "--app", help="Show diff for one app only"),
    output: str = typer.Option("table", "--output", "-o", help="table|json|yaml"),
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
):
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

    except ConfigValidationError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)
    except Exception as e:
        log.exception("Diff failed", error=str(e))
        typer.echo(f"\n✗ Diff failed: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(
        help="""Show current configuration.

Examples:
    synos config
""",
)
def config(
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
):
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
        typer.echo(f"  Suspended Apps:   {config_obj.suspended_apps_csv or '-'}")
        
    except ConfigValidationError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)
    except Exception as e:
        log.exception("Failed to show config", error=str(e))
        raise typer.Exit(code=1)


@app.command(
        "set",
        help="""Update operator runtime settings (interval/prune/protected/max-concurrent).

Examples:
    synos set --show
    synos set --interval 120 --yes
    synos set --prune --max-concurrent 5 --yes
    synos set --protected-apps synoscd-operator,api-gateway --yes
""",
)
def set_operator_settings(
    interval: Optional[int] = typer.Option(None, "--interval", help="Set reconciliation interval in seconds"),
    prune: Optional[bool] = typer.Option(None, "--prune/--no-prune", help="Enable or disable prune"),
    protected_apps: Optional[str] = typer.Option(None, "--protected-apps", help="Comma-separated protected app names"),
    max_concurrent: Optional[int] = typer.Option(None, "--max-concurrent", help="Max concurrent reconciles"),
    operator_app_name: str = typer.Option("synoscd-operator", "--operator-app-name", help="Operator ACA app name"),
    resource_group: Optional[str] = typer.Option(None, "--resource-group", help="Operator resource group"),
    show: bool = typer.Option(False, "--show", help="Show current operator settings"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply without interactive confirmation"),
):
    setup_logging()

    if interval is not None and interval <= 0:
        typer.echo("Interval must be greater than 0 seconds.", err=True)
        raise typer.Exit(code=2)
    if max_concurrent is not None and max_concurrent <= 0:
        typer.echo("Max concurrent must be greater than 0.", err=True)
        raise typer.Exit(code=2)

    try:
        rg = _detect_operator_rg(operator_app_name, resource_group)
        current_env = _fetch_operator_env_map(rg, operator_app_name)

        if show:
            _print_operator_settings(current_env)
            return

        updates: dict[str, str] = {}
        if interval is not None:
            updates[OPERATOR_ENV_KEYS["interval"]] = str(interval)
        if prune is not None:
            updates[OPERATOR_ENV_KEYS["prune"]] = "true" if prune else "false"
        if protected_apps is not None:
            updates[OPERATOR_ENV_KEYS["protected_apps"]] = protected_apps
        if max_concurrent is not None:
            updates[OPERATOR_ENV_KEYS["max_concurrent"]] = str(max_concurrent)

        if not updates:
            typer.echo("No changes requested. Use --show or provide one of --interval/--prune/--protected-apps/--max-concurrent.", err=True)
            raise typer.Exit(code=2)

        typer.echo("Planned updates:")
        for key, value in updates.items():
            before = current_env.get(key, "<unset>")
            typer.echo(f"  {key}: {before} -> {value}")

        if not yes and not typer.confirm("Apply these settings to the operator now?"):
            typer.echo("Cancelled.")
            raise typer.Exit(code=1)

        _apply_operator_env_updates(rg, operator_app_name, updates)
        typer.echo("✓ Operator settings updated")
        typer.echo("ℹ️  New settings apply on the updated operator revision.")

    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        typer.echo(f"✗ Failed to update operator settings: {message}", err=True)
        raise typer.Exit(code=1)
    except FileNotFoundError as exc:
        missing = exc.filename or "az"
        typer.echo(f"✗ Command not found: {missing}", err=True)
        raise typer.Exit(code=1)
    except RuntimeError as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(code=1)


def _update_suspended_apps(
    app_name: str,
    suspend: bool,
    operator_app_name: str,
    resource_group: Optional[str],
    yes: bool,
) -> None:
    rg = _detect_operator_rg(operator_app_name, resource_group)
    current_env = _fetch_operator_env_map(rg, operator_app_name)
    current = set(parse_csv(current_env.get(OPERATOR_ENV_KEYS["suspended_apps"], "")))

    if suspend:
        if app_name in current:
            typer.echo(f"'{app_name}' is already suspended.")
            return
        updated = sorted(current | {app_name})
    else:
        if app_name not in current:
            typer.echo(f"'{app_name}' is not suspended.")
            return
        updated = sorted(current - {app_name})

    csv_value = ",".join(updated)
    typer.echo("Planned update:")
    typer.echo(
        f"  {OPERATOR_ENV_KEYS['suspended_apps']}: {current_env.get(OPERATOR_ENV_KEYS['suspended_apps'], '<unset>')} -> {csv_value or '<empty>'}"
    )

    if not yes and not typer.confirm("Apply this change to the operator now?"):
        typer.echo("Cancelled.")
        raise typer.Exit(code=1)

    _apply_operator_env_updates(
        rg,
        operator_app_name,
        {OPERATOR_ENV_KEYS["suspended_apps"]: csv_value},
    )
    action = "Suspended" if suspend else "Resumed"
    typer.echo(f"✓ {action} '{app_name}'")


@app.command(
        "suspend",
        help="""Suspend reconciliation for an app (runtime override).

Examples:
    synos suspend demo-app --yes
""",
)
def suspend_app(
    name: str = typer.Argument(..., help="App name to suspend reconciliation for"),
    operator_app_name: str = typer.Option("synoscd-operator", "--operator-app-name", help="Operator ACA app name"),
    resource_group: Optional[str] = typer.Option(None, "--resource-group", help="Operator resource group"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply without interactive confirmation"),
):
    setup_logging()
    try:
        _update_suspended_apps(name, True, operator_app_name, resource_group, yes)
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        typer.echo(f"✗ Failed to suspend app: {message}", err=True)
        raise typer.Exit(code=1)
    except FileNotFoundError as exc:
        missing = exc.filename or "az"
        typer.echo(f"✗ Command not found: {missing}", err=True)
        raise typer.Exit(code=1)
    except RuntimeError as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(code=1)


@app.command(
        "resume",
        help="""Resume reconciliation for an app (runtime override).

Examples:
    synos resume demo-app --yes
""",
)
def resume_app(
    name: str = typer.Argument(..., help="App name to resume reconciliation for"),
    operator_app_name: str = typer.Option("synoscd-operator", "--operator-app-name", help="Operator ACA app name"),
    resource_group: Optional[str] = typer.Option(None, "--resource-group", help="Operator resource group"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply without interactive confirmation"),
):
    setup_logging()
    try:
        _update_suspended_apps(name, False, operator_app_name, resource_group, yes)
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        typer.echo(f"✗ Failed to resume app: {message}", err=True)
        raise typer.Exit(code=1)
    except FileNotFoundError as exc:
        missing = exc.filename or "az"
        typer.echo(f"✗ Command not found: {missing}", err=True)
        raise typer.Exit(code=1)
    except RuntimeError as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(code=1)


@app.command(
        "describe",
        help="""Describe an app (alias for 'status app').

Examples:
    synos describe demo-app
    synos describe demo-app -o yaml
    synos describe demo-app --watch
""",
)
def describe(
    name: str = typer.Argument(..., help="App name"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Refresh continuously"),
    interval: int = typer.Option(5, "--interval", help="Refresh interval in seconds"),
):
    """Describe an app (alias for 'status app')."""
    status.show_app(
        name=name,
        output=output,
        config_path=config_path,
        watch=watch,
        interval=interval,
    )


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
