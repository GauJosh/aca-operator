# SynosCD Configuration
# Environment and settings management

from pydantic_settings import BaseSettings
from typing import Optional


class SynoscdConfig(BaseSettings):
    """SynosCD operator configuration."""

    # GitHub App integration
    github_app_id: str
    github_app_private_key: str
    github_app_installation_id: str
    github_repo_owner: str
    github_repo_name: str

    # Azure
    azure_subscription_id: str
    azure_resource_group: str
    azure_container_app_environment: str

    # Reconciliation
    reconcile_interval_seconds: int = 300  # 5 minutes
    webhook_enabled: bool = True
    max_concurrent_reconciles: int = 3

    # Logging
    log_level: str = "INFO"
    structured_logs: bool = True

    # Git
    git_clone_path: Optional[str] = None  # defaults to /tmp/synoscd-git
    git_commit_message_prefix: str = "[SynosCD]"

    class Config:
        env_prefix = "SYNOSCD_"
        case_sensitive = False
