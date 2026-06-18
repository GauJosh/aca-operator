# SynosCD Schema Definitions
# Kubernetes-style resource definitions for Azure Container Apps

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

# ============================================================================
# API Version and Kind Enums
# ============================================================================


class APIVersion(str, Enum):
    """Supported API versions."""

    V1ALPHA1 = "synoscd.io/v1alpha1"


class Kind(str, Enum):
    """Supported resource kinds."""

    APP = "App"
    PROJECT = "Project"


# ============================================================================
# Condition and Status Models
# ============================================================================


class ConditionStatus(str, Enum):
    """Status of a condition."""

    TRUE = "True"
    FALSE = "False"
    UNKNOWN = "Unknown"


class Condition(BaseModel):
    """A condition in resource status."""

    type: str
    status: ConditionStatus
    last_transition_time: datetime = Field(default_factory=datetime.utcnow)
    reason: str = ""
    message: str = ""


# ============================================================================
# App Resource
# ============================================================================


class ContainerImage(BaseModel):
    """Container image specification."""

    name: str = Field(..., description="Container name")
    image: str = Field(..., description="Image URI (e.g., myacr.azurecr.io/app:latest)")
    cpu: Optional[float] = Field(default=0.25, description="CPU cores (0.25-4.0)")
    memory: Optional[str] = Field(default="0.5Gi", description="Memory (0.5Gi-4Gi)")


class EnvVar(BaseModel):
    """Environment variable."""

    name: str
    value: Optional[str] = None
    value_from: Optional[Dict[str, str]] = Field(default=None, alias="valueFrom")


class IngressConfig(BaseModel):
    """Ingress configuration."""

    enabled: bool = False
    external: bool = True
    target_port: int = Field(default=80, alias="targetPort")
    allowed_origins: Optional[List[str]] = Field(default=None, alias="allowedOrigins")


class ScaleConfig(BaseModel):
    """Auto-scale configuration."""

    min_replicas: int = Field(default=1, alias="minReplicas")
    max_replicas: int = Field(default=10, alias="maxReplicas")


class AppSpec(BaseModel):
    """Specification for an App resource."""

    containers: List[ContainerImage] = Field(..., description="Container definitions")
    environment: Optional[List[EnvVar]] = Field(
        default=None, description="Environment variables"
    )
    ingress: Optional[IngressConfig] = Field(
        default=None, description="Ingress settings"
    )
    scale: Optional[ScaleConfig] = Field(default=None, description="Scale settings")
    secrets: Optional[Dict[str, str]] = Field(
        default=None, description="Secret references (key vault)"
    )
    suspend: bool = Field(
        default=False, description="Suspend reconciliation for this app"
    )


class AppStatus(BaseModel):
    """Status of an App resource."""

    conditions: List[Condition] = Field(default_factory=list)
    last_synced_at: Optional[datetime] = Field(default=None, alias="lastSyncedAt")
    last_synced_from_commit: Optional[str] = Field(
        default=None, alias="lastSyncedFromCommit"
    )
    last_error: Optional[str] = Field(default=None, alias="lastError")
    observed_generation: int = Field(default=0, alias="observedGeneration")


class AppMetadata(BaseModel):
    """Metadata for an App resource."""

    name: str = Field(..., description="App name (must match Azure Container App name)")
    namespace: Optional[str] = Field(
        default="default", description="Logical namespace (for multi-tenancy)"
    )
    labels: Optional[Dict[str, str]] = Field(
        default=None, description="Labels for filtering/grouping"
    )
    annotations: Optional[Dict[str, str]] = Field(
        default=None, description="Annotations for metadata"
    )


class App(BaseModel):
    """SynosCD App resource definition."""

    api_version: APIVersion = Field(default=APIVersion.V1ALPHA1, alias="apiVersion")
    kind: Kind = Field(default=Kind.APP)
    metadata: AppMetadata
    spec: AppSpec
    status: Optional[AppStatus] = Field(default_factory=AppStatus)


# ============================================================================
# Project Resource (multi-app grouping)
# ============================================================================


class ProjectSpec(BaseModel):
    """Specification for a Project resource."""

    apps: List[str] = Field(
        default_factory=list, description="App names in this project"
    )
    defaults: Optional[Dict[str, Any]] = Field(
        default=None, description="Default spec fields for all apps"
    )
    policy: Optional[Dict[str, Any]] = Field(
        default=None, description="Policy constraints (e.g., allowed registries)"
    )


class ProjectStatus(BaseModel):
    """Status of a Project resource."""

    conditions: List[Condition] = Field(default_factory=list)
    synced_apps: int = Field(default=0, alias="syncedApps")
    failed_apps: int = Field(default=0, alias="failedApps")


class ProjectMetadata(BaseModel):
    """Metadata for a Project resource."""

    name: str = Field(..., description="Project name")
    namespace: Optional[str] = Field(default="default")
    labels: Optional[Dict[str, str]] = Field(default=None)
    annotations: Optional[Dict[str, str]] = Field(default=None)


class Project(BaseModel):
    """SynosCD Project resource definition (groups multiple apps)."""

    api_version: APIVersion = Field(default=APIVersion.V1ALPHA1, alias="apiVersion")
    kind: Kind = Field(default=Kind.PROJECT)
    metadata: ProjectMetadata
    spec: ProjectSpec
    status: Optional[ProjectStatus] = Field(default_factory=ProjectStatus)


# ============================================================================
# Union and Parsing
# ============================================================================

Resource = App | Project


def parse_resource(data: Dict[str, Any]) -> Resource:
    """Parse raw YAML/dict into the appropriate resource type."""
    kind = data.get("kind")
    if kind == "App":
        return App.model_validate(data)
    elif kind == "Project":
        return Project.model_validate(data)
    else:
        raise ValueError(f"Unknown kind: {kind}")
