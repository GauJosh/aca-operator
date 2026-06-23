"""Status commands - detailed view of app status."""

import asyncio
import json
import typer
from typing import Optional
from synoscd.logger import setup_logging, get_logger
from synoscd.commands.common import build_clients, format_table

log = get_logger(__name__)
app = typer.Typer(help="Detailed app status")


@app.command("app")
def show_app(
    name: str = typer.Argument(..., help="App name"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Refresh continuously"),
    interval: int = typer.Option(5, "--interval", help="Refresh interval in seconds"),
):
    """Show detailed status for a specific app."""
    setup_logging()
    
    try:
        _, _, aca_client, _ = build_clients(config_path)

        while True:
            live_app = asyncio.run(aca_client.get_app(name))
            if not live_app:
                typer.echo(f"✗ App '{name}' not found in Azure", err=True)
                raise typer.Exit(code=1)

            props = live_app.get("properties", {})

            data = {
                "name": live_app.get("name", "-"),
                "location": live_app.get("location", "-"),
                "status": "✓ Active" if props.get("latestReadyRevisionName") else "✗ Inactive",
                "provisioning_state": props.get("provisioningState", "Unknown"),
                "latest_ready_revision": props.get("latestReadyRevisionName", "-"),
                "running_status": props.get("runningStatus", "-"),
                "replicas": props.get("replicas", "-"),
                "outbound_ip_addresses": ", ".join(props.get("outboundIpAddresses", [])) or "-",
            }

            # Get error details if provisioning failed
            if props.get("provisioningState") == "Failed":
                data["provisioning_error"] = str(
                    props.get("provisioningError", {}).get("message", "-")
                )
                deploy_errors = props.get("deployment", {}).get("error", {})
                if deploy_errors:
                    data["deployment_error"] = str(deploy_errors.get("message", "-"))

            if output == "json":
                typer.echo(json.dumps(data, indent=2))
            else:  # table
                typer.echo(f"\n📦 App Status: {name}\n")
                typer.echo(f"  Status:                {data['status']}")
                typer.echo(f"  Provisioning State:    {data['provisioning_state']}")
                typer.echo(f"  Latest Ready Revision: {data['latest_ready_revision']}")
                typer.echo(f"  Running Status:        {data['running_status']}")
                typer.echo(f"  Replicas:              {data['replicas']}")
                typer.echo(f"  Location:              {data['location']}")
                typer.echo(f"  Outbound IPs:          {data['outbound_ip_addresses']}")

                if "provisioning_error" in data:
                    typer.echo(
                        f"\n  ⚠️  Provisioning Error: {data.get('provisioning_error', '-')}"
                    )
                if "deployment_error" in data:
                    typer.echo(
                        f"  ⚠️  Deployment Error:   {data.get('deployment_error', '-')}"
                    )

            if not watch:
                break
            typer.echo(f"\n⏳ Refreshing in {interval}s ... (Ctrl+C to stop)")
            import time

            time.sleep(interval)

    except KeyboardInterrupt as exc:
        raise typer.Exit(code=0) from exc
    except Exception as e:
        log.exception("Failed to get app status", app_name=name, error=str(e))
        raise typer.Exit(code=1)


@app.command("all")
def show_all_statuses(
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Refresh continuously"),
    interval: int = typer.Option(5, "--interval", help="Refresh interval in seconds"),
):
    """Show status for all apps."""
    setup_logging()
    
    try:
        _, _, aca_client, _ = build_clients(config_path)

        while True:
            live_list = asyncio.run(aca_client.list_apps())

            rows = []
            for live_app in live_list:
                props = live_app.get("properties", {})
                provisioning = props.get("provisioningState", "Unknown")
                ready_rev = props.get("latestReadyRevisionName")
                status_icon = "✓" if provisioning == "Succeeded" and ready_rev else "✗"
                running = props.get("runningStatus", "-")

                rows.append({
                    "status": status_icon,
                    "name": live_app.get("name", "-"),
                    "provisioning": provisioning,
                    "status_detail": running,
                    "ready_revision": ready_rev or "-",
                })

            if output == "json":
                typer.echo(json.dumps(rows, indent=2))
            else:  # table
                if not rows:
                    typer.echo("No apps found")
                    return

                headers = ["STATUS", "NAME", "PROVISIONING", "STATUS_DETAIL", "READY_REV"]
                table_rows = [
                    [
                        row["status"],
                        row["name"],
                        row["provisioning"],
                        row["status_detail"],
                        row["ready_revision"],
                    ]
                    for row in rows
                ]
                typer.echo(format_table(headers, table_rows))

            if not watch:
                break
            typer.echo(f"\n⏳ Refreshing in {interval}s ... (Ctrl+C to stop)")
            import time

            time.sleep(interval)

    except KeyboardInterrupt as exc:
        raise typer.Exit(code=0) from exc
    except Exception as e:
        log.exception("Failed to get all app statuses", error=str(e))
        raise typer.Exit(code=1)
