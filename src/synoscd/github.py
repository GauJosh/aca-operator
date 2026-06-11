# GitHub Integration
# Fetch and parse desired state from GitHub repo using GitHub App

import httpx
import jwt
import time
import yaml
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from synoscd.logger import get_logger

log = get_logger(__name__)


class GitHubAppClient:
    """GitHub App client for repository access."""

    def __init__(
        self,
        app_id: str,
        private_key: str,
        installation_id: str,
        repo_owner: str,
        repo_name: str,
    ):
        self.app_id = app_id
        self.private_key = private_key
        self.installation_id = installation_id
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def _get_jwt(self) -> str:
        """Generate JWT for GitHub App authentication."""
        now = int(time.time())
        payload = {
            "iat": now,
            "exp": now + 300,  # 5 min validity
            "iss": self.app_id,
        }
        return jwt.encode(self.private_key, payload, algorithm="RS256")

    def _get_access_token(self) -> str:
        """Get access token for the installation."""
        if self._token and self._token_expires_at and datetime.utcnow() < self._token_expires_at:
            return self._token

        jwt_token = self._get_jwt()
        url = f"https://api.github.com/app/installations/{self.installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        with httpx.Client() as client:
            response = client.post(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        self._token = data["token"]
        # Expire 10 seconds before actual expiry to be safe
        expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        self._token_expires_at = expires_at - timedelta(seconds=10)

        log.msg("GitHub App access token acquired", installation_id=self.installation_id)
        return self._token

    async def fetch_file_content(self, file_path: str, ref: str = "main") -> str:
        """Fetch file content from GitHub repo."""
        token = self._get_access_token()
        url = (
            f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/"
            f"contents/{file_path}?ref={ref}"
        )
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.raw",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        log.msg("Fetched file from GitHub", file_path=file_path, ref=ref)
        return response.text

    async def fetch_directory_yaml_files(
        self, directory: str = ".", ref: str = "main"
    ) -> Dict[str, Any]:
        """Fetch all YAML files from a directory and parse them."""
        token = self._get_access_token()
        url = (
            f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/"
            f"contents/{directory}?ref={ref}"
        )
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        resources = {}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            items = response.json()

        yaml_items = [item for item in items if item["name"].endswith(".yaml") or item["name"].endswith(".yml")]

        for item in yaml_items:
            try:
                content = await self.fetch_file_content(item["path"], ref=ref)
                # Parse YAML (could contain multiple documents)
                docs = yaml.safe_load_all(content)
                for doc in docs:
                    if doc and isinstance(doc, dict):
                        name = doc.get("metadata", {}).get("name", item["name"])
                        resources[name] = doc
                        log.msg("Parsed YAML resource", file=item["name"], name=name)
            except Exception as e:
                log.exception("Failed to parse YAML file", file=item["name"], error=str(e))

        return resources

    async def get_latest_commit(self, ref: str = "main") -> str:
        """Get latest commit SHA on ref."""
        token = self._get_access_token()
        url = (
            f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/"
            f"commits/{ref}"
        )
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        return data["sha"]
