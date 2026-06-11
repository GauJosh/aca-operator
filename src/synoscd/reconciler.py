# Reconciliation Engine
# Main loop for comparing desired (Git) vs live (Azure) state and applying changes

import asyncio
from typing import List, Optional, Dict, Any
from synoscd.schema import App, Resource, parse_resource
from synoscd.github import GitHubAppClient
from synoscd.aca import ACAClient
from synoscd.logger import get_logger

log = get_logger(__name__)


class ReconcileError(Exception):
    """Reconciliation error."""
    pass


class Reconciler:
    """Main reconciliation loop."""

    def __init__(self, github: GitHubAppClient, aca: ACAClient):
        self.github = github
        self.aca = aca

    async def sync_once(self) -> Dict[str, Any]:
        """Run a single reconciliation pass."""
        log.msg("Starting reconciliation pass")

        try:
            # 1. Fetch desired state from GitHub
            desired_resources = await self._fetch_desired_state()
            log.msg("Fetched desired state from GitHub", count=len(desired_resources))

            # 2. Fetch live state from Azure
            live_apps = await self.aca.list_apps()
            log.msg("Fetched live apps from Azure", count=len(live_apps))

            # 3. Reconcile each resource
            results = await self._reconcile_resources(desired_resources)
            log.msg("Reconciliation pass complete", results=results)

            return results

        except Exception as e:
            log.exception("Reconciliation pass failed", error=str(e))
            raise ReconcileError(str(e))

    async def _fetch_desired_state(self) -> Dict[str, Resource]:
        """Fetch desired state from GitHub."""
        try:
            raw_resources = await self.github.fetch_directory_yaml_files()
            resources = {}

            for name, data in raw_resources.items():
                try:
                    resource = parse_resource(data)
                    resources[name] = resource
                except Exception as e:
                    log.exception("Failed to parse resource from GitHub", name=name, error=str(e))

            return resources
        except Exception as e:
            log.exception("Failed to fetch desired state from GitHub", error=str(e))
            raise

    async def _reconcile_resources(self, desired: Dict[str, Resource]) -> Dict[str, Any]:
        """Reconcile desired resources against live state."""
        results = {
            "synced": [],
            "failed": [],
            "skipped": [],
        }

        for name, resource in desired.items():
            try:
                if isinstance(resource, App):
                    await self._reconcile_app(resource)
                    results["synced"].append(name)
                    log.msg("Reconciled app", app_name=name)
                else:
                    # Project or other kind - skip for now
                    results["skipped"].append(name)
            except Exception as e:
                results["failed"].append({"name": name, "error": str(e)})
                log.exception("Failed to reconcile resource", name=name, error=str(e))

        return results

    async def _reconcile_app(self, app: App) -> None:
        """Reconcile a single App resource."""
        if app.spec.suspend:
            log.msg("App is suspended, skipping", app_name=app.metadata.name)
            return

        # Check if app should be managed by SynosCD
        if not self._is_managed(app):
            log.msg("App not managed by SynosCD, skipping", app_name=app.metadata.name)
            return

        # Fetch live state
        live_app = await self.aca.get_app(app.metadata.name)

        # Diff and apply if needed
        if self._needs_update(app, live_app):
            log.msg("App differs from desired state, applying", app_name=app.metadata.name)
            await self.aca.create_or_update_app(app.metadata.name, app.spec.model_dump())
        else:
            log.msg("App matches desired state", app_name=app.metadata.name)

    def _is_managed(self, app: App) -> bool:
        """Check if app is labeled as SynosCD-managed."""
        if not app.metadata.labels:
            return False
        return app.metadata.labels.get("synoscd.io/managed") == "true"

    def _needs_update(self, desired: App, live: Optional[Dict[str, Any]]) -> bool:
        """Check if live app differs from desired."""
        if live is None:
            return True  # App doesn't exist, needs creation
        # TODO: implement actual diff logic
        return False


class OperatorLoop:
    """Long-running operator loop."""

    def __init__(
        self,
        reconciler: Reconciler,
        interval_seconds: int = 300,
        max_concurrent: int = 3,
    ):
        self.reconciler = reconciler
        self.interval_seconds = interval_seconds
        self.max_concurrent = max_concurrent
        self._running = False

    async def start(self):
        """Start the operator loop."""
        self._running = True
        log.msg("Starting operator loop", interval_seconds=self.interval_seconds)

        while self._running:
            try:
                await self.reconciler.sync_once()
            except Exception as e:
                log.exception("Error in operator loop, will retry", error=str(e))

            await asyncio.sleep(self.interval_seconds)

    def stop(self):
        """Stop the operator loop."""
        self._running = False
        log.msg("Stopping operator loop")
