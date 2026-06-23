"""Logs commands - stream and view logs."""

import subprocess
import typer
from typing import Optional
from synoscd.logger import setup_logging, get_logger
from synoscd.commands.common import build_clients

log = get_logger(__name__)
app = typer.Typer(help="Stream and view logs")


@app.command("app")
def app_logs(
    name: str = typer.Argument(..., help="App name"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to tail"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log stream"),
    config_path: Optional[str] = typer.Option(None, help="Path to config file (to get resource group)"),
):
    """Stream logs from a container app (wrapper around 'az containerapp logs')."""
    setup_logging()
    
    try:
        rg = "synoscd-dev"
        try:
            config, _, _, _ = build_clients(config_path)
            rg = config.azure_resource_group
        except Exception:
            pass
        
        # Build az containerapp logs command
        cmd = [
            "az", "containerapp", "logs", "show",
            "--name", name,
            "--resource-group", rg,
            "--tail", str(tail),
        ]
        
        if follow:
            cmd.append("--follow")
        
        typer.echo(f"📋 Streaming logs for '{name}' (Ctrl+C to exit)...\n")
        
        # Run the command
        try:
            subprocess.run(cmd, check=True, text=True)
        except subprocess.CalledProcessError as e:
            typer.echo(f"✗ Failed to get logs: {e.stderr or str(e)}", err=True)
            raise typer.Exit(code=1)
        except FileNotFoundError as exc:
            typer.echo("✗ 'az' CLI not found. Please install Azure CLI.", err=True)
            raise typer.Exit(code=1) from exc
            
    except KeyboardInterrupt as exc:
        typer.echo("\n\nLogs stopped")
        raise typer.Exit(code=0) from exc
    except Exception as e:
        log.exception("Failed to get logs", app_name=name, error=str(e))
        raise typer.Exit(code=1)


@app.command()
def operator(
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to tail"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log stream"),
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
):
    """Stream logs from the SynosCD operator."""
    setup_logging()
    
    try:
        rg = "synoscd-dev"
        try:
            config, _, _, _ = build_clients(config_path)
            rg = config.azure_resource_group
        except Exception:
            pass
        
        # Build az containerapp logs command for operator
        cmd = [
            "az", "containerapp", "logs", "show",
            "--name", "synoscd-operator",
            "--resource-group", rg,
            "--tail", str(tail),
        ]
        
        if follow:
            cmd.append("--follow")
        
        typer.echo("📋 Streaming operator logs (Ctrl+C to exit)...\n")
        
        # Run the command
        try:
            subprocess.run(cmd, check=True, text=True)
        except subprocess.CalledProcessError as e:
            typer.echo(f"✗ Failed to get operator logs: {e.stderr or str(e)}", err=True)
            raise typer.Exit(code=1)
        except FileNotFoundError as exc:
            typer.echo("✗ 'az' CLI not found. Please install Azure CLI.", err=True)
            raise typer.Exit(code=1) from exc
            
    except KeyboardInterrupt as exc:
        typer.echo("\n\nOperator logs stopped")
        raise typer.Exit(code=0) from exc
    except Exception as e:
        log.exception("Failed to get operator logs", error=str(e))
        raise typer.Exit(code=1)
