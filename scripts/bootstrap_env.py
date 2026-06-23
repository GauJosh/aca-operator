#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


def _run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    resolved_cmd = _resolve_command(cmd)
    return subprocess.run(resolved_cmd, check=check, text=True, capture_output=True)


def _to_windows_path(path: str) -> str:
    if os.name != "nt":
        return path

    match = re.match(r"^/([a-zA-Z])/(.+)$", path)
    if not match:
        return path

    drive = match.group(1).upper()
    remainder = match.group(2).replace("/", "\\")
    return f"{drive}:\\{remainder}"


def _resolve_command(cmd: List[str]) -> List[str]:
    if not cmd:
        return cmd

    executable = cmd[0]
    if os.name != "nt":
        return cmd

    if os.path.isabs(executable) or executable.startswith("/"):
        cmd[0] = _to_windows_path(executable)
        return cmd

    from shutil import which

    resolved = which(executable)
    if resolved:
        cmd[0] = _to_windows_path(resolved)
    return cmd


def _run_tsv(cmd: List[str]) -> str:
    result = _run(cmd)
    return result.stdout.strip()


def _run_json(cmd: List[str]) -> object:
    result = _run(cmd)
    text = result.stdout.strip()
    if not text:
        return {}
    return json.loads(text)


def _has_command(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def _ensure_az_login() -> None:
    try:
        _run(["az", "account", "show"])
    except subprocess.CalledProcessError:
        print("🔐 Azure login required. Opening login...", file=sys.stderr)
        _run(["az", "login"])


def _parse_repo_url(repo_url: str) -> tuple[str, str]:
    path = repo_url
    if path.startswith("git@github.com:"):
        path = path.replace("git@github.com:", "", 1)
    if path.startswith("https://github.com/"):
        path = path.replace("https://github.com/", "", 1)
    if path.endswith(".git"):
        path = path[:-4]

    if "/" not in path:
        raise ValueError(f"Invalid GitHub repo URL: {repo_url}")
    owner, repo = path.split("/", 1)
    return owner, repo


def _detect_rg(operator_app_name: str, rg_hint: Optional[str]) -> str:
    if rg_hint:
        return rg_hint

    try:
        rg = _run_tsv(
            [
                "az",
                "resource",
                "list",
                "--resource-type",
                "Microsoft.App/containerApps",
                "--name",
                operator_app_name,
                "--query",
                "[0].resourceGroup",
                "-o",
                "tsv",
            ]
        )
        if rg:
            return rg
    except subprocess.CalledProcessError:
        pass

    rg = _run_tsv(
        [
            "az",
            "containerapp",
            "env",
            "list",
            "--query",
            "[0].resourceGroup",
            "-o",
            "tsv",
        ]
    )
    if not rg:
        raise RuntimeError("Could not auto-detect Azure resource group")
    return rg


def _detect_ace(rg: str, ace_hint: Optional[str]) -> str:
    if ace_hint:
        return ace_hint
    ace = _run_tsv(
        [
            "az",
            "containerapp",
            "env",
            "list",
            "-g",
            rg,
            "--query",
            "[0].name",
            "-o",
            "tsv",
        ]
    )
    if not ace:
        raise RuntimeError(f"Could not auto-detect ACA Environment in resource group '{rg}'")
    return ace


def _get_secret(vault_name: str, secret_name: str) -> str:
    value = _run_tsv(
        [
            "az",
            "keyvault",
            "secret",
            "show",
            "--vault-name",
            vault_name,
            "--name",
            secret_name,
            "--query",
            "value",
            "-o",
            "tsv",
        ]
    )
    if not value:
        raise RuntimeError(f"Secret '{secret_name}' in vault '{vault_name}' is empty or missing")
    return value


def _repo_from_operator_env(rg: str, operator_app_name: str) -> tuple[Optional[str], Optional[str]]:
    try:
        env_data = _run_json(
            [
                "az",
                "containerapp",
                "show",
                "-g",
                rg,
                "-n",
                operator_app_name,
                "--query",
                "properties.template.containers[0].env",
                "-o",
                "json",
            ]
        )
        if not isinstance(env_data, list):
            return None, None
        owner = None
        repo = None
        for item in env_data:
            if not isinstance(item, dict):
                continue
            if item.get("name") == "SYNOSCD_GITHUB_REPO_OWNER":
                owner = item.get("value")
            if item.get("name") == "SYNOSCD_GITHUB_REPO_NAME":
                repo = item.get("value")
        return owner, repo
    except subprocess.CalledProcessError:
        return None, None


def _repo_from_git_remote() -> tuple[Optional[str], Optional[str]]:
    try:
        remote = _run_tsv(["git", "remote", "get-url", "origin"])
        if not remote:
            return None, None
        return _parse_repo_url(remote)
    except (subprocess.CalledProcessError, ValueError):
        return None, None


def _build_env(args: argparse.Namespace) -> Dict[str, str]:
    if not _has_command("az"):
        raise RuntimeError("Azure CLI ('az') not found in PATH. Install Azure CLI and restart your shell.")

    _ensure_az_login()

    sub_id = _run_tsv(["az", "account", "show", "--query", "id", "-o", "tsv"])
    rg = _detect_rg(args.operator_app_name, args.rg_hint)
    ace = _detect_ace(rg, args.ace_hint)

    app_id = _get_secret(args.vault_name, args.app_id_secret)
    installation_id = _get_secret(args.vault_name, args.installation_id_secret)
    private_key = _get_secret(args.vault_name, args.private_key_secret)

    owner: Optional[str]
    repo: Optional[str]
    if args.config_repo_url:
        owner, repo = _parse_repo_url(args.config_repo_url)
    else:
        owner, repo = _repo_from_operator_env(rg, args.operator_app_name)
        if not owner or not repo:
            owner, repo = _repo_from_git_remote()

    if not owner or not repo:
        raise RuntimeError(
            "Could not auto-detect config repo owner/name. Use --config-repo-url https://github.com/<owner>/<repo>.git"
        )

    return {
        "SYNOSCD_GITHUB_APP_ID": app_id,
        "SYNOSCD_GITHUB_APP_PRIVATE_KEY": private_key,
        "SYNOSCD_GITHUB_APP_INSTALLATION_ID": installation_id,
        "SYNOSCD_GITHUB_REPO_OWNER": owner,
        "SYNOSCD_GITHUB_REPO_NAME": repo,
        "SYNOSCD_GITHUB_CONFIG_PATH": args.config_path,
        "SYNOSCD_AZURE_SUBSCRIPTION_ID": sub_id,
        "SYNOSCD_AZURE_RESOURCE_GROUP": rg,
        "SYNOSCD_AZURE_CONTAINER_APP_ENVIRONMENT": ace,
        "SYNOSCD_RECONCILE_INTERVAL_SECONDS": str(args.interval),
        "SYNOSCD_PRUNE_ENABLED": "true" if args.prune_enabled else "false",
        "SYNOSCD_PROTECTED_APPS_CSV": args.protected_apps_csv,
    }


def _print_summary(env_vars: Dict[str, str], vault_name: str) -> None:
    print("✅ SynosCD environment loaded")
    print(f"   Vault:         {vault_name}")
    print(f"   Subscription:  {env_vars['SYNOSCD_AZURE_SUBSCRIPTION_ID']}")
    print(f"   ResourceGroup: {env_vars['SYNOSCD_AZURE_RESOURCE_GROUP']}")
    print(f"   ACE:           {env_vars['SYNOSCD_AZURE_CONTAINER_APP_ENVIRONMENT']}")
    print(f"   ConfigRepo:    {env_vars['SYNOSCD_GITHUB_REPO_OWNER']}/{env_vars['SYNOSCD_GITHUB_REPO_NAME']}")
    print(f"   ConfigPath:    {env_vars['SYNOSCD_GITHUB_CONFIG_PATH']}")
    print()
    print("🔎 Loaded variables (private key hidden):")
    for key in sorted(env_vars.keys()):
        value = env_vars[key]
        if key == "SYNOSCD_GITHUB_APP_PRIVATE_KEY":
            value = "***hidden***"
        print(f"{key}={value}")


def _write_env_file(path: Path, env_vars: Dict[str, str]) -> None:
    lines = [
        "# Auto-generated by scripts/bootstrap_env.py",
        "# shellcheck shell=bash",
        "",
    ]
    for key in sorted(env_vars.keys()):
        lines.append(f"export {key}={shlex.quote(env_vars[key])}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    if os.name != "nt":
        os.chmod(path, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap SynosCD environment from Azure + Key Vault")
    parser.add_argument("--vault-name", default="synoscd-vault")
    parser.add_argument("--app-id-secret", default="github-app-id")
    parser.add_argument("--installation-id-secret", default="github-app-installation-id")
    parser.add_argument("--private-key-secret", default="github-app-private-key")
    parser.add_argument("--operator-app-name", default="synoscd-operator")
    parser.add_argument("--rg-hint", default="synoscd-dev")
    parser.add_argument("--ace-hint", default="synoscd-ace")
    parser.add_argument("--config-repo-url", default="https://github.com/GauJosh/my-aca-config.git")
    parser.add_argument("--config-path", default="apps")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--prune-enabled", action="store_true")
    parser.add_argument("--protected-apps-csv", default="synoscd-operator")
    parser.add_argument("--print-exports", action="store_true", help="Print shell export lines")
    parser.add_argument("--write-env-file", default="", help="Write export file (e.g. .synoscd.env)")
    parser.add_argument("--run", nargs=argparse.REMAINDER, help="Run command with loaded env (e.g. --run synos get apps)")

    args = parser.parse_args()

    try:
        env_vars = _build_env(args)
    except FileNotFoundError as exc:
        missing = exc.filename or "required command"
        print(f"❌ Command not found: {missing}. Ensure it is installed and available in PATH.", file=sys.stderr)
        return 1
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.print_exports:
        for key in sorted(env_vars.keys()):
            print(f"export {key}={shlex.quote(env_vars[key])}")
        return 0

    if args.write_env_file:
        env_path = Path(args.write_env_file)
        _write_env_file(env_path, env_vars)
        print(f"📝 Wrote env file: {env_path}")

    _print_summary(env_vars, args.vault_name)

    if args.run:
        cmd = args.run
        print()
        print(f"▶ Running with loaded env: {' '.join(shlex.quote(part) for part in cmd)}")
        child_env = os.environ.copy()
        child_env.update(env_vars)
        completed = subprocess.run(cmd, env=child_env, check=False)
        return completed.returncode

    print()
    print("▶ Next (no source needed):")
    print("   python scripts/bootstrap_env.py --run synos config")
    print("   python scripts/bootstrap_env.py --run synos get source")
    print("   python scripts/bootstrap_env.py --run synos get apps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
