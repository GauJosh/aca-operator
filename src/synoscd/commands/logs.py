"""Logs commands - stream and view logs."""

import os
import re
import shlex
import subprocess
from shutil import which
import typer
from typing import Optional
from synoscd.logger import setup_logging, get_logger
from synoscd.commands.common import build_clients

log = get_logger(__name__)
app = typer.Typer(help="Stream and view logs")


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


def _run_az(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True, text=True)
    except FileNotFoundError:
        if os.name != "nt":
            raise

        bash_path = which("bash")
        if not bash_path:
            raise

        rendered = " ".join(shlex.quote(part) for part in cmd)
        subprocess.run(
            [_to_windows_path(bash_path), "-lc", rendered], check=True, text=True
        )


@app.command("app")
def app_logs(
    name: str = typer.Argument(..., help="App name"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to tail"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log stream"),
    config_path: Optional[str] = typer.Option(
        None, help="Path to config file (to get resource group)"
    ),
):
    """Stream logs from a container app (wrapper around 'az containerapp logs').

    Examples:
      synos logs app demo-app
      synos logs app demo-app -f
      synos logs app demo-app -n 50
    """
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
            _resolve_az(),
            "containerapp",
            "logs",
            "show",
            "--name",
            name,
            "--resource-group",
            rg,
            "--tail",
            str(tail),
        ]

        if follow:
            cmd.append("--follow")

        if follow:
            typer.echo(f"📋 Streaming logs for '{name}' (Ctrl+C to exit)...\n")
        else:
            typer.echo(
                f"📋 Showing last {tail} logs for '{name}' (use --follow/-f to stream).\n"
            )

        # Run the command
        try:
            _run_az(cmd)
        except subprocess.CalledProcessError as e:
            typer.echo(f"✗ Failed to get logs: {e.stderr or str(e)}", err=True)
            raise typer.Exit(code=1)
        except FileNotFoundError as exc:
            typer.echo(
                "✗ Azure CLI not found in this shell PATH. Install Azure CLI or launch this shell after az is available.",
                err=True,
            )
            raise typer.Exit(code=1) from exc

    except KeyboardInterrupt as exc:
        typer.echo("\n\nLogs stopped")
        raise typer.Exit(code=0) from exc
    except typer.Exit:
        raise
    except Exception as e:
        log.exception("Failed to get logs", app_name=name, error=str(e))
        raise typer.Exit(code=1)


@app.command()
def operator(
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to tail"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log stream"),
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
):
    """Stream logs from the SynosCD operator.

    Examples:
      synos logs operator
      synos logs operator -f
      synos logs operator -n 200
    """
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
            _resolve_az(),
            "containerapp",
            "logs",
            "show",
            "--name",
            "synoscd-operator",
            "--resource-group",
            rg,
            "--tail",
            str(tail),
        ]

        if follow:
            cmd.append("--follow")

        if follow:
            typer.echo("📋 Streaming operator logs (Ctrl+C to exit)...\n")
        else:
            typer.echo(
                f"📋 Showing last {tail} operator logs (use --follow/-f to stream).\n"
            )

        # Run the command
        try:
            _run_az(cmd)
        except subprocess.CalledProcessError as e:
            typer.echo(f"✗ Failed to get operator logs: {e.stderr or str(e)}", err=True)
            raise typer.Exit(code=1)
        except FileNotFoundError as exc:
            typer.echo(
                "✗ Azure CLI not found in this shell PATH. Install Azure CLI or launch this shell after az is available.",
                err=True,
            )
            raise typer.Exit(code=1) from exc

    except KeyboardInterrupt as exc:
        typer.echo("\n\nOperator logs stopped")
        raise typer.Exit(code=0) from exc
    except typer.Exit:
        raise
    except Exception as e:
        log.exception("Failed to get operator logs", error=str(e))
        raise typer.Exit(code=1)
