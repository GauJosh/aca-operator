"""Get commands - view SynosCD and source state (like 'flux get')."""

import asyncio
import json
import typer
from typing import Optional
from synoscd.logger import setup_logging, get_logger
from synoscd.commands.common import (
    build_clients,
    parse_csv,
    fetch_operator_env_map,
    format_table,
    ConfigValidationError,
)

log = get_logger(__name__)
app = typer.Typer(help="View SynosCD and source state (like 'flux get')")


@app.command()
def apps(
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
):
    """List applications (like 'flux get ks' for Kustomizations).

    Examples:
      synos get apps
      synos get apps -o yaml
    """
    setup_logging()
    
    try:
        config, _, aca_client, reconciler = build_clients(config_path)
        live_operator_env = fetch_operator_env_map(config.azure_resource_group)
        runtime_suspended = set(
            parse_csv(live_operator_env.get("SYNOSCD_SUSPENDED_APPS_CSV", ""))
        )
        desired = asyncio.run(reconciler.fetch_desired_state())
        live_list = asyncio.run(aca_client.list_apps())
        live_map = {item.get("name"): item for item in live_list if item.get("name")}
        
        rows = []
        for resource in desired.values():
            if resource.kind.value != "App":
                continue
            
            app_name = resource.metadata.name
            desired_suspended = resource.spec.suspend if hasattr(resource.spec, 'suspend') else False
            suspended = bool(desired_suspended or app_name in runtime_suspended)
            managed = (
                bool(resource.metadata.labels)
                and resource.metadata.labels.get("synoscd.io/managed") == "true"
            )
            
            live = live_map.get(app_name)
            if live:
                provisioning = live.get("properties", {}).get("provisioningState", "Unknown")
                ready_rev = live.get("properties", {}).get("latestReadyRevisionName", "-")
                status_icon = "✓" if provisioning == "Succeeded" and ready_rev != "-" else "✗"
            else:
                provisioning = "NotFound"
                ready_rev = "-"
                status_icon = "✗"
            
            rows.append({
                "status": status_icon,
                "name": app_name,
                "managed": "Yes" if managed else "No",
                "suspended": "Yes" if suspended else "No",
                "provisioning": provisioning,
                "ready_revision": ready_rev,
            })
        
        if output == "json":
            typer.echo(json.dumps(rows, indent=2))
        elif output == "yaml":
            import yaml
            typer.echo(yaml.dump(rows, default_flow_style=False))
        else:  # table
            if not rows:
                typer.echo("No applications found")
                return
            
            headers = ["STATUS", "NAME", "MANAGED", "SUSPENDED", "PROVISIONING", "READY_REV"]
            table_rows = [
                [
                    row["status"],
                    row["name"],
                    row["managed"],
                    row["suspended"],
                    row["provisioning"],
                    row["ready_revision"],
                ]
                for row in rows
            ]
            typer.echo(format_table(headers, table_rows))
            
    except ConfigValidationError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)
    except Exception as e:
        log.exception("Failed to get apps", error=str(e))
        raise typer.Exit(code=1)


@app.command()
def source(
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
):
    """Show Git source configuration (like 'flux get source git').

    Examples:
        synos get source
        synos get source -o yaml
"""
    setup_logging()
    
    try:
        config, github_client, _, _ = build_clients(config_path)
        latest_commit = asyncio.run(github_client.get_latest_commit())
        
        data = {
            "type": "git",
            "owner": config.github_repo_owner,
            "repo": config.github_repo_name,
            "path": config.github_config_path,
            "ref": "main",
            "latest_commit": latest_commit[:8] if latest_commit else "unknown",
            "url": f"https://github.com/{config.github_repo_owner}/{config.github_repo_name}",
        }
        
        if output == "json":
            typer.echo(json.dumps(data, indent=2))
        elif output == "yaml":
            import yaml

            typer.echo(yaml.dump(data, default_flow_style=False, sort_keys=False))
        else:  # table
            headers = ["TYPE", "OWNER/REPO", "PATH", "REF", "LATEST_COMMIT", "URL"]
            rows = [[
                data["type"],
                f"{data['owner']}/{data['repo']}",
                data["path"],
                data["ref"],
                data["latest_commit"],
                data["url"],
            ]]
            typer.echo(format_table(headers, rows))
            
    except ConfigValidationError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)
    except Exception as e:
        log.exception("Failed to get source", error=str(e))
        raise typer.Exit(code=1)


@app.command("status")
def get_status(
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
):
    """Show SynosCD summary status (similar to Flux get views).

        Examples:
            synos get status
            synos get status -o yaml
    """
    setup_logging()
    
    try:
        _, _, aca_client, reconciler = build_clients(config_path)
        desired = asyncio.run(reconciler.fetch_desired_state())
        live_list = asyncio.run(aca_client.list_apps())
        
        desired_apps = [r for r in desired.values() if r.kind.value == "App"]
        managed_desired = [
            app for app in desired_apps
            if app.metadata.labels and app.metadata.labels.get("synoscd.io/managed") == "true"
        ]
        
        healthy_live = 0
        for live in live_list:
            props = live.get("properties", {})
            provisioning = (props.get("provisioningState") or "").lower()
            if provisioning == "succeeded" and props.get("latestReadyRevisionName"):
                healthy_live += 1
        
        data = {
            "desired_apps": len(desired_apps),
            "managed_apps": len(managed_desired),
            "live_apps": len(live_list),
            "healthy_apps": healthy_live,
            "prune_enabled": reconciler.prune_enabled,
            "protected_apps": len(reconciler.protected_apps),
        }
        
        if output == "json":
            typer.echo(json.dumps(data, indent=2))
        elif output == "yaml":
            import yaml

            typer.echo(yaml.dump(data, default_flow_style=False, sort_keys=False))
        else:  # table
            typer.echo("\nSynosCD Status Summary:")
            typer.echo(f"  Desired Apps:    {data['desired_apps']}")
            typer.echo(f"  Managed Apps:    {data['managed_apps']}")
            typer.echo(f"  Live Apps:       {data['live_apps']}")
            typer.echo(f"  Healthy Apps:    {data['healthy_apps']}")
            typer.echo(f"  Prune Enabled:   {'Yes' if data['prune_enabled'] else 'No'}")
            typer.echo(f"  Protected Apps:  {data['protected_apps']}")
            
    except ConfigValidationError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)
    except Exception as e:
        log.exception("Failed to get summary", error=str(e))
        raise typer.Exit(code=1)
