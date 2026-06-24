# SynosCD - GitOps Operator for Azure Container Apps

[![Build, Test, Scan & Tag](https://github.com/GauJosh/aca-operator/actions/workflows/build-scan-tag.yml/badge.svg)](https://github.com/GauJosh/aca-operator/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Declarative, GitOps-based application management for Azure Container Apps.** Deploy ACA apps from Git with automatic drift detection, health-aware reconciliation, and safety guardrails.

SynosCD brings **Flux-like GitOps** to Azure Container Apps:
- ✅ **Git as Source of Truth** - YAML manifests define desired state
- ✅ **Automatic Drift Healing** - Operator continuously reconciles desired↔live state
- ✅ **Health-Aware Reconciliation** - Failed/unready apps trigger automatic re-apply
- ✅ **Safe by Default** - Managed ownership tagging + protected app list prevent accidental deletion
- ✅ **Local Development** - Full support for `az login` based testing
- ✅ **Production Grade** - Structured JSON logging, ARM validation, LRO polling

## What SynosCD Supports

- Pull-based reconciliation loop (configurable interval)
- GitHub App authentication for config repo access
- Real ARM create/update/delete/list/get calls for ACA resources
- Health-aware reconciliation (re-apply if app is not healthy)
- Managed ownership tagging on apps (`synoscd-managed=true`)
- Optional prune mode for managed apps missing from Git
- Protected app list to avoid deleting critical apps (e.g. `synoscd-operator`)

## Architecture Model

- **One operator per ACE/environment**
- **One ops repo as source of truth** (recommended)
- **Apps defined as YAML** under `apps/` (or custom config path)
- **Terraform/Bicep owns platform foundation** (ACE, identity, network, etc.)
- **SynosCD owns app-level reconciliation**

## App Manifest (Git Contract)

```yaml
apiVersion: synoscd.io/v1alpha1
kind: App
metadata:
  name: demo-app
  labels:
    synoscd.io/managed: "true"
spec:
  containers:
    - name: app
      image: mcr.microsoft.com/azuredocs/containerapps-helloworld:latest
      cpu: 0.25
      memory: 0.5Gi
  ingress:
    enabled: true
    external: true
    targetPort: 80
  scale:
    minReplicas: 1
    maxReplicas: 3
  suspend: false
```

## Environment Variables

### Required

- `SYNOSCD_GITHUB_APP_ID`
- `SYNOSCD_GITHUB_APP_PRIVATE_KEY`
- `SYNOSCD_GITHUB_APP_INSTALLATION_ID`
- `SYNOSCD_GITHUB_REPO_OWNER`
- `SYNOSCD_GITHUB_REPO_NAME`
- `SYNOSCD_AZURE_SUBSCRIPTION_ID`
- `SYNOSCD_AZURE_RESOURCE_GROUP`
- `SYNOSCD_AZURE_CONTAINER_APP_ENVIRONMENT`

### Common Optional

- `SYNOSCD_GITHUB_CONFIG_PATH` (default: `apps`)
- `SYNOSCD_RECONCILE_INTERVAL_SECONDS` (default: `300`)
- `SYNOSCD_AZURE_MANAGED_IDENTITY_CLIENT_ID` (needed for user-assigned MI in ACA)
- `SYNOSCD_PRUNE_ENABLED` (default: `false`)
- `SYNOSCD_PROTECTED_APPS_CSV` (default: `synoscd-operator`)

## Run Locally (Development)

Local run is supported via `DefaultAzureCredential`.

### 1) Setup

```bash
python -m venv venv
source venv/bin/activate  # Windows Git Bash: source venv/Scripts/activate
pip install -e .
```

You can run SynosCD in any of these ways:

```bash
synos --help
python -m synoscd --help
python src/synoscd/cli.py --help
```

The package is configured for standard installation on Windows, Linux, and macOS.

## Install / Download

### Recommended: pipx or pip install

The easiest way to use SynosCD is from a published release:

```bash
pipx install synoscd
# or
pip install synoscd
```

### GitHub Release downloads

Each tagged release publishes:
- `synoscd-<version>.tar.gz` source distribution
- `synoscd-<version>-py3-none-any.whl` wheel
- Standalone `synos` binaries for Linux, macOS, and Windows

Use the standalone binary if you want a direct download and run experience.

#### Direct-run prerequisites

The standalone binaries still require configuration at runtime:
- Azure credentials or managed identity access
- SynosCD environment variables set
- Access to the GitHub App private key / Key Vault secret source

Example:

```bash
export SYNOSCD_GITHUB_APP_ID=<app-id>
export SYNOSCD_GITHUB_APP_PRIVATE_KEY="$(cat private-key.pem)"
export SYNOSCD_GITHUB_APP_INSTALLATION_ID=<installation-id>
export SYNOSCD_GITHUB_REPO_OWNER=<owner>
export SYNOSCD_GITHUB_REPO_NAME=<repo>
export SYNOSCD_AZURE_SUBSCRIPTION_ID=<sub-id>
export SYNOSCD_AZURE_RESOURCE_GROUP=<resource-group>
export SYNOSCD_AZURE_CONTAINER_APP_ENVIRONMENT=<ace-name>

synos get apps
```

On Windows PowerShell:

```powershell
$env:SYNOSCD_GITHUB_APP_ID = '<app-id>'
$env:SYNOSCD_GITHUB_APP_PRIVATE_KEY = Get-Content .\private-key.pem -Raw
$env:SYNOSCD_GITHUB_APP_INSTALLATION_ID = '<installation-id>'
$env:SYNOSCD_GITHUB_REPO_OWNER = '<owner>'
$env:SYNOSCD_GITHUB_REPO_NAME = '<repo>'
$env:SYNOSCD_AZURE_SUBSCRIPTION_ID = '<sub-id>'
$env:SYNOSCD_AZURE_RESOURCE_GROUP = '<resource-group>'
$env:SYNOSCD_AZURE_CONTAINER_APP_ENVIRONMENT = '<ace-name>'

synos get apps
```

### 2) Authenticate Azure

```bash
az login
az account set --subscription <your-subscription-id>
```

### 3) Export config and run

```bash
export SYNOSCD_GITHUB_APP_ID=<app-id>
export SYNOSCD_GITHUB_APP_PRIVATE_KEY="$(cat private-key.pem)"
export SYNOSCD_GITHUB_APP_INSTALLATION_ID=<installation-id>
export SYNOSCD_GITHUB_REPO_OWNER=<owner>
export SYNOSCD_GITHUB_REPO_NAME=<repo>
export SYNOSCD_AZURE_SUBSCRIPTION_ID=<sub-id>
export SYNOSCD_AZURE_RESOURCE_GROUP=<resource-group>
export SYNOSCD_AZURE_CONTAINER_APP_ENVIRONMENT=<ace-name>
export SYNOSCD_GITHUB_CONFIG_PATH=apps
export SYNOSCD_RECONCILE_INTERVAL_SECONDS=30

synos operator
```

### 3b) One-command auto bootstrap from Key Vault

If your GitHub App secrets are in Key Vault (for example `synoscd-vault`), you can auto-load everything with one command:

```bash
python scripts/bootstrap_env.py --run synos get apps
```

This is the recommended UX (cross-platform): no `source`, no `eval`, no subshell confusion.

Other examples:

```bash
python scripts/bootstrap_env.py --run synos config
python scripts/bootstrap_env.py --run synos get source
python scripts/bootstrap_env.py --run synos get apps
```

You can also generate shell exports if needed:

```bash
python scripts/bootstrap_env.py --print-exports
```

This script auto-detects subscription, resource group, ACE, and loads GitHub App secrets from AKV:

- `github-app-id`
- `github-app-installation-id`
- `github-app-private-key`

Optional overrides:

```bash
python scripts/bootstrap_env.py \
  --vault-name synoscd-vault \
  --rg-hint synoscd-dev \
  --ace-hint <ace-name> \
  --config-repo-url https://github.com/<owner>/<repo>.git \
  --run synos get source
```

Convenience wrappers:

```bash
# Git Bash / Linux / macOS
./scripts/synos-env.sh get apps

# PowerShell
./scripts/synos-env.ps1 get apps
```

After it runs:

```bash
python scripts/bootstrap_env.py --run synos config
python scripts/bootstrap_env.py --run synos get source
python scripts/bootstrap_env.py --run synos get apps
```

## Deploy Operator to ACA (Podman + ACR)

```bash
ACR_NAME="synoscdacr"
IMAGE="synoscdacr.azurecr.io/synoscd:v0.2.6"

podman build -t "$IMAGE" .
TOKEN=$(az acr login -n "$ACR_NAME" --expose-token --query accessToken -o tsv)
podman login synoscdacr.azurecr.io -u 00000000-0000-0000-0000-000000000000 -p "$TOKEN"
podman push "$IMAGE"

MI_CLIENT_ID=$(az identity show -g synoscd-dev -n synoscd-identity --query clientId -o tsv)

az containerapp update -n synoscd-operator -g synoscd-dev \
  --image "$IMAGE" \
  --set-env-vars \
    SYNOSCD_AZURE_MANAGED_IDENTITY_CLIENT_ID="$MI_CLIENT_ID" \
    SYNOSCD_RECONCILE_INTERVAL_SECONDS=30 \
    SYNOSCD_PRUNE_ENABLED=false \
    SYNOSCD_PROTECTED_APPS_CSV="synoscd-operator"
```

## How Reconciliation Works

Each cycle:
1. Fetch YAML resources from Git (`apps/` by default)
2. Parse into SynosCD resources (`App`, `Project`)
3. List live ACA apps from Azure
4. For each managed `App`:
   - If missing or drifted, apply desired state via ARM
   - If live app health is failed/not ready, force reconcile
5. Optionally prune managed apps missing from Git (if enabled)

## Drift Heal, Safety, and Prune

- **Drift heal**: Enabled by default via desired-vs-live comparison
- **Health-aware reconcile**: Failed/unready app is re-applied even when spec is unchanged
- **Ownership tag**: SynosCD writes `synoscd-managed=true` on managed apps
- **Prune mode**: Disabled by default (`SYNOSCD_PRUNE_ENABLED=false`)
- **Protected apps**: Never pruned if listed in `SYNOSCD_PROTECTED_APPS_CSV`

### Prune behavior (when enabled)

Prune deletes only apps that are:
- tagged as managed by SynosCD, and
- not present in desired Git state, and
- not in protected app list

## CLI Commands

- `synos operator` — run operator loop
- `synos sync` — run one reconciliation pass now
- `synos config` — show active SynosCD configuration
- `synos bootstrap` — bootstrap/config validation helper
- `synos reconcile source` — Flux-like full reconcile from Git source
- `synos reconcile app <name>` — Flux-like targeted reconcile for one App
- `synos get apps [-o table|json|yaml]` — list desired Apps with live health context
- `synos get source [-o table|json]` — show Git source details + latest commit
- `synos get status [-o table|json]` — show reconciliation summary
- `synos status app <name>` — show detailed live status for one app
- `synos status all` — show detailed live status for all apps
- `synos logs app <name>` — stream logs for one ACA app
- `synos logs operator` — stream logs for the SynosCD operator

## Release / Distribution Strategy

SynosCD publishes multiple distribution formats from GitHub Releases:

| Format | Best for |
| --- | --- |
| Source tarball (`.tar.gz`) | Contributors and source installs |
| Wheel (`.whl`) | Standard Python installs and pip mirrors |
| Standalone binary (`synos` / `synos.exe`) | Direct download and run with env vars already configured |

Recommended usage:
1. **Most users**: `pipx install synoscd`
2. **Python environments**: `pip install synoscd`
3. **No-Python client machines**: download the standalone release binary

If you use a standalone binary, you still need to set the same SynosCD env vars before running the CLI.

### Flux-style mapping

- `flux reconcile source git` → `synos reconcile source`
- `flux reconcile kustomization <name>` → `synos reconcile app <name>`
- `flux get source git` → `synos get source`
- `flux get ks` / `flux get hr` → `synos get apps` (App-centric model)

### Resource model

SynosCD is intentionally simpler than Flux.

- Flux uses separate resource types such as `GitRepository`, `Kustomization`, and `HelmRelease`
- SynosCD uses a single app-centric model
- Git connectivity is configured on the operator itself
- The operator pulls manifests directly and reconciles them to Azure Container Apps

Today, the primary Git contract is the `App` manifest. You do not need separate `Source` or `Kustomization` manifests unless SynosCD later grows into a multi-source or multi-tenant platform.

## Troubleshooting

### Operator revision fails with `ErrImagePull`

Image tag not found in ACR. Verify tags:
```bash
az acr repository show-tags -n synoscdacr --repository synos -o table
```

### Azure tag validation failure (`InvalidTagNameCharacters`)

Use ARM-safe tags (SynosCD now uses `synoscd-managed=true`).

### App keeps failing after successful `PUT 201`

Check app resource provisioning + revision state:
```bash
az containerapp show -n <app> -g <rg> --query "{provisioning:properties.provisioningState,latest:properties.latestRevisionName,ready:properties.latestReadyRevisionName}" -o jsonc
az containerapp revision list -n <app> -g <rg> -o table
```

If Azure CLI log streaming has extension issues, use activity log:
```bash
APP_ID=$(az containerapp show -n <app> -g <rg> --query id -o tsv)
az monitor activity-log list --resource-id "$APP_ID" --status Failed --offset 2h -o jsonc
```

### CPU/memory validation fails

ACA requires valid CPU/memory combinations (for example `0.25` + `0.5Gi`, `0.5` + `1Gi`).

## Repository Layout

```
src/synoscd/
  __init__.py
  schema.py
  config.py
  logger.py
  github.py
  aca.py
  reconciler.py
  cli.py

examples/
docs/
```

## Current Maturity

- Core GitOps loop: implemented
- ARM app create/update/list/get/delete: implemented
- Drift heal + health-aware retry: implemented
- Safe ownership tagging + optional prune: implemented
- Multi-repo orchestration: not implemented (single repo per operator recommended)
