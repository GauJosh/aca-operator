# Azure Container Apps API Client
# Fetch and reconcile live ACA resources

import asyncio
from typing import Optional, Dict, Any, List
from azure.identity import DefaultAzureCredential
import httpx
from synoscd.logger import get_logger

log = get_logger(__name__)


class ACAClient:
    """Client for Azure Container Apps operations."""

    API_VERSION = "2024-03-01"
    MANAGED_TAG_KEY = "synoscd-managed"
    MANAGED_TAG_VALUE = "true"

    def __init__(
        self,
        subscription_id: str,
        resource_group: str,
        environment_name: str,
        managed_identity_client_id: Optional[str] = None,
    ):
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.environment_name = environment_name
        self.credential = DefaultAzureCredential(
            managed_identity_client_id=managed_identity_client_id
        )
        self._base_url = "https://management.azure.com"
        self._cached_location: Optional[str] = None

    def _token(self) -> str:
        return self.credential.get_token("https://management.azure.com/.default").token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token()}",
            "Content-Type": "application/json",
        }

    def _app_resource_id(self, app_name: str) -> str:
        return (
            f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.App/containerApps/{app_name}"
        )

    def _env_resource_id(self) -> str:
        return (
            f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.App/managedEnvironments/{self.environment_name}"
        )

    async def _request_json(
        self, method: str, path: str, payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = f"{self._base_url}{path}"
        params = {"api-version": self.API_VERSION}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
                method,
                url,
                params=params,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            if response.content:
                return response.json()
            return {}

    async def _wait_lro(self, initial_response: Dict[str, Any]) -> Dict[str, Any]:
        """Poll ARM long-running operation until completion if needed."""
        status = initial_response.get("properties", {}).get("provisioningState")
        if status and status.lower() in {"succeeded", "failed", "canceled"}:
            return initial_response

        app_name = initial_response.get("name")
        if not app_name:
            return initial_response

        for _ in range(90):
            await asyncio.sleep(2)
            current = await self.get_app(app_name)
            if not current:
                continue
            provisioning_state = (
                current.get("properties", {}).get("provisioningState", "").lower()
            )
            if provisioning_state in {"succeeded", "failed", "canceled"}:
                return current

        return initial_response

    async def _get_environment_location(self) -> str:
        if self._cached_location:
            return self._cached_location
        env = await self._request_json("GET", self._env_resource_id())
        self._cached_location = env.get("location", "eastus")
        return self._cached_location

    @staticmethod
    def _build_env_vars(
        environment: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        env_vars: List[Dict[str, Any]] = []
        if not environment:
            return env_vars

        for entry in environment:
            name = entry.get("name")
            if not name:
                continue
            if entry.get("value") is not None:
                env_vars.append({"name": name, "value": entry.get("value")})
                continue

            value_from = entry.get("value_from") or entry.get("valueFrom") or {}
            secret_ref = value_from.get("secretRef") or value_from.get("secret_ref")
            if secret_ref:
                env_vars.append({"name": name, "secretRef": secret_ref})

        return env_vars

    @staticmethod
    def _normalize_desired(spec: Dict[str, Any]) -> Dict[str, Any]:
        containers = []
        for container in spec.get("containers", []) or []:
            containers.append(
                {
                    "name": container.get("name"),
                    "image": container.get("image"),
                    "cpu": float(container.get("cpu", 0.25)),
                    "memory": str(container.get("memory", "0.5Gi")),
                    "env": ACAClient._build_env_vars(spec.get("environment")),
                }
            )

        ingress = spec.get("ingress") or {}
        scale = spec.get("scale") or {}

        return {
            "containers": sorted(containers, key=lambda item: item.get("name") or ""),
            "ingress": {
                "enabled": bool(ingress.get("enabled", False)),
                "external": bool(ingress.get("external", True)),
                "targetPort": int(
                    ingress.get("target_port", ingress.get("targetPort", 80))
                ),
            },
            "scale": {
                "minReplicas": int(
                    scale.get("min_replicas", scale.get("minReplicas", 1))
                ),
                "maxReplicas": int(
                    scale.get("max_replicas", scale.get("maxReplicas", 10))
                ),
            },
        }

    @staticmethod
    def normalize_desired(spec: Dict[str, Any]) -> Dict[str, Any]:
        """Public wrapper for normalizing desired app spec."""
        return ACAClient._normalize_desired(spec)

    @staticmethod
    def _validate_resources(spec: Dict[str, Any]) -> None:
        allowed_memory_by_cpu = {
            0.25: {"0.5Gi"},
            0.5: {"1Gi"},
            0.75: {"1.5Gi"},
            1.0: {"2Gi"},
            1.25: {"2.5Gi"},
            1.5: {"3Gi"},
            1.75: {"3.5Gi"},
            2.0: {"4Gi"},
        }

        for container in spec.get("containers", []) or []:
            cpu = float(container.get("cpu", 0.25))
            memory = str(container.get("memory", "0.5Gi"))
            allowed_memory = allowed_memory_by_cpu.get(cpu)
            if allowed_memory is None:
                raise ValueError(
                    f"Invalid CPU value '{cpu}' for container '{container.get('name')}'. "
                    f"Allowed: {sorted(allowed_memory_by_cpu.keys())}"
                )
            if memory not in allowed_memory:
                raise ValueError(
                    f"Invalid memory '{memory}' for cpu '{cpu}' in container '{container.get('name')}'. "
                    f"Allowed memory for this CPU: {sorted(allowed_memory)}"
                )

    @staticmethod
    def _normalize_live(app: Dict[str, Any]) -> Dict[str, Any]:
        props = app.get("properties", {})
        template = props.get("template", {})
        config = props.get("configuration", {})

        containers = []
        for container in template.get("containers", []) or []:
            resources = container.get("resources", {})
            env = container.get("env", []) or []
            normalized_env = []
            for entry in env:
                item = {"name": entry.get("name")}
                if "value" in entry:
                    item["value"] = entry.get("value")
                if "secretRef" in entry:
                    item["secretRef"] = entry.get("secretRef")
                normalized_env.append(item)

            containers.append(
                {
                    "name": container.get("name"),
                    "image": container.get("image"),
                    "cpu": float(resources.get("cpu", 0.25)),
                    "memory": str(resources.get("memory", "0.5Gi")),
                    "env": normalized_env,
                }
            )

        ingress = config.get("ingress") or {}
        scale = template.get("scale") or {}

        return {
            "containers": sorted(containers, key=lambda item: item.get("name") or ""),
            "ingress": {
                "enabled": bool(ingress),
                "external": bool(ingress.get("external", True)),
                "targetPort": int(ingress.get("targetPort", 80)),
            },
            "scale": {
                "minReplicas": int(scale.get("minReplicas", 1)),
                "maxReplicas": int(scale.get("maxReplicas", 10)),
            },
        }

    @staticmethod
    def normalize_live(app: Dict[str, Any]) -> Dict[str, Any]:
        """Public wrapper for normalizing live ACA app state."""
        return ACAClient._normalize_live(app)

    async def needs_update(
        self, desired_spec: Dict[str, Any], live_app: Optional[Dict[str, Any]]
    ) -> bool:
        if not live_app:
            return True

        properties = live_app.get("properties", {})
        provisioning_state = (properties.get("provisioningState") or "").lower()
        latest_revision = properties.get("latestRevisionName")
        latest_ready_revision = properties.get("latestReadyRevisionName")

        if provisioning_state != "succeeded" or not latest_ready_revision:
            log.msg(
                "Live app not healthy, forcing reconcile",
                provisioning_state=provisioning_state or "unknown",
                latest_revision=latest_revision,
                latest_ready_revision=latest_ready_revision,
            )
            return True

        return self._normalize_desired(desired_spec) != self._normalize_live(live_app)

    def is_managed_by_synoscd(self, app: Dict[str, Any]) -> bool:
        tags = app.get("tags") or {}
        return tags.get(self.MANAGED_TAG_KEY) == self.MANAGED_TAG_VALUE

    async def get_app(self, app_name: str) -> Optional[Dict[str, Any]]:
        """Fetch a live ACA app resource."""
        log.msg(
            "Fetching ACA app", app_name=app_name, resource_group=self.resource_group
        )
        path = self._app_resource_id(app_name)
        try:
            return await self._request_json("GET", path)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return None
            raise

    async def list_apps(self) -> List[Dict[str, Any]]:
        """List all ACA apps in the environment."""
        log.msg(
            "Listing ACA apps",
            environment=self.environment_name,
            resource_group=self.resource_group,
        )
        path = (
            f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"
            "/providers/Microsoft.App/containerApps"
        )
        data = await self._request_json("GET", path)
        return data.get("value", [])

    async def create_or_update_app(self, app_name: str, spec: Dict[str, Any]) -> bool:
        """Create or update an ACA app."""
        log.msg("Creating/updating ACA app", app_name=app_name, spec=spec)
        self._validate_resources(spec)
        location = await self._get_environment_location()

        desired = self._normalize_desired(spec)
        payload: Dict[str, Any] = {
            "location": location,
            "tags": {
                self.MANAGED_TAG_KEY: self.MANAGED_TAG_VALUE,
            },
            "properties": {
                "managedEnvironmentId": self._env_resource_id(),
                "template": {
                    "containers": [],
                    "scale": desired["scale"],
                },
            },
        }

        for container in desired["containers"]:
            payload["properties"]["template"]["containers"].append(
                {
                    "name": container["name"],
                    "image": container["image"],
                    "resources": {
                        "cpu": container["cpu"],
                        "memory": container["memory"],
                    },
                    "env": container["env"],
                }
            )

        if desired["ingress"]["enabled"]:
            payload["properties"]["configuration"] = {
                "ingress": {
                    "external": desired["ingress"]["external"],
                    "targetPort": desired["ingress"]["targetPort"],
                    "transport": "auto",
                }
            }

        if spec.get("secrets"):
            payload.setdefault("properties", {}).setdefault("configuration", {})[
                "secrets"
            ] = [
                {"name": key, "value": value}
                for key, value in (spec.get("secrets") or {}).items()
            ]

        path = self._app_resource_id(app_name)
        try:
            response = await self._request_json("PUT", path, payload=payload)
        except httpx.HTTPStatusError as error:
            response_text = error.response.text
            log.exception(
                "ARM create/update failed",
                app_name=app_name,
                status_code=error.response.status_code,
                response=response_text,
            )
            raise
        final = await self._wait_lro(response)
        state = (final.get("properties", {}).get("provisioningState") or "").lower()
        if state != "succeeded":
            properties = final.get("properties", {})
            log.error(
                "ACA app provisioning not succeeded",
                app_name=app_name,
                provisioning_state=state or "unknown",
                latest_revision=properties.get("latestRevisionName"),
                latest_ready_revision=properties.get("latestReadyRevisionName"),
                running_status=properties.get("runningStatus"),
                deployment_errors=properties.get("deploymentErrors"),
                provisioning_errors=properties.get("provisioningErrors"),
            )
            return False
        return True

    async def delete_app(self, app_name: str) -> bool:
        """Delete an ACA app."""
        log.msg("Deleting ACA app", app_name=app_name)
        path = self._app_resource_id(app_name)
        try:
            await self._request_json("DELETE", path)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return True
            raise
        return True

    async def get_app_secrets(self, app_name: str) -> Dict[str, str]:
        """Fetch secrets for an ACA app."""
        # TODO: integrate with Key Vault
        return {}
