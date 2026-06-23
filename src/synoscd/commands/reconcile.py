"""Reconcile commands - control reconciliation behavior."""

import asyncio
import typer
from typing import Optional
from synoscd.logger import setup_logging, get_logger
from synoscd.commands.common import build_clients

log = get_logger(__name__)
app = typer.Typer(help="Control reconciliation behavior")


@app.command("source")
def reconcile_source(
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch mode (stream updates)"),
):
    """Trigger source reconciliation immediately (like 'flux reconcile source git')."""
    setup_logging()
    log.msg("Triggering reconciliation now")
    
    try:
        _, _, _, reconciler = build_clients(config_path)
        
        while True:
            result = asyncio.run(reconciler.sync_once())
            
            # Format output
            synced_count = len(result.get("synced", []))
            failed_count = len(result.get("failed", []))
            pruned_count = len(result.get("pruned", []))
            
            status = "✓" if not result.get("failed") else "✗"
            typer.echo(f"\n{status} Reconciliation complete")
            typer.echo(f"  Synced: {synced_count}")
            typer.echo(f"  Failed: {failed_count}")
            typer.echo(f"  Pruned: {pruned_count}")
            
            if result.get("failed"):
                typer.echo("\n  Failed apps:")
                for app_name, error in result["failed"].items():
                    typer.echo(f"    - {app_name}: {error}")
            
            if not watch:
                break
            
            # Wait before next reconciliation in watch mode
            typer.echo("\n  Waiting 5s for next reconciliation (Ctrl+C to exit)...")
            import time
            
            time.sleep(5)
            
    except KeyboardInterrupt as exc:
        typer.echo("\nReconciliation stopped")
        raise typer.Exit(code=0) from exc
    except Exception as e:
        log.exception("Reconciliation failed", error=str(e))
        raise typer.Exit(code=1)


@app.command("app")
def reconcile_app(
    name: str = typer.Argument(..., help="App name to reconcile"),
    config_path: Optional[str] = typer.Option(None, help="Path to config file"),
):
    """Reconcile a specific app (like 'flux reconcile kustomization')."""
    setup_logging()
    log.msg("Reconciling app", app_name=name)
    
    try:
        _, _, _, reconciler = build_clients(config_path)
        result = asyncio.run(reconciler.sync_app(name))
        
        typer.echo(f"\n✓ Reconciliation complete for '{name}'")
        typer.echo(f"  Status: {result.get('status', 'unknown')}")
        if result.get("error"):
            typer.echo(f"  Error: {result['error']}")
            raise typer.Exit(code=1)
            
    except Exception as e:
        log.exception("App reconciliation failed", app_name=name, error=str(e))
        raise typer.Exit(code=1)
