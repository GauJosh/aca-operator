# SynosCD

GitOps-style operator for Azure Container Apps (ACA) running inside an ACA Environment (ACE).

## Current Status

Implementation: **Phase 1-2 (MVP Reconciler)**

- ✅ Schema and CRD-like resource definitions (App, Project)
- ✅ GitHub App integration (fetch desired state)
- ✅ Reconciliation engine (pull-based sync loop)
- ✅ CLI with bootstrap, operator, sync, diff, status commands
- 🚧 Azure API integration (placeholder for ACA operations)
- 🚧 Drift detection and rollback
- 🚧 Webhook-triggered sync

## Quick Start

### Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # on Windows: venv\Scripts\activate
pip install -e .
```

### Run Operator

```bash
export SYNOSCD_GITHUB_APP_ID=your_app_id
export SYNOSCD_GITHUB_APP_PRIVATE_KEY=$(cat private_key.pem)
export SYNOSCD_GITHUB_APP_INSTALLATION_ID=your_installation_id
export SYNOSCD_GITHUB_REPO_OWNER=your_org
export SYNOSCD_GITHUB_REPO_NAME=your_repo
export SYNOSCD_AZURE_SUBSCRIPTION_ID=your_sub_id
export SYNOSCD_AZURE_RESOURCE_GROUP=your_rg
export SYNOSCD_AZURE_CONTAINER_APP_ENVIRONMENT=your_ace_name

synos operator
```

### Define Apps in Git

Place YAML files in your repo (see `examples/`):

```yaml
apiVersion: synoscd.io/v1alpha1
kind: App
metadata:
  name: my-api
  labels:
    synoscd.io/managed: "true"
spec:
  containers:
    - name: api
      image: myacr.azurecr.io/api:latest
      cpu: 0.5
      memory: 1Gi
  ingress:
    enabled: true
    targetPort: 8080
```

## Project Structure

```
src/synoscd/
  __init__.py      - Package init
  schema.py        - K8s-like CRD definitions (App, Project)
  config.py        - Configuration management
  logger.py        - Structured logging setup
  github.py        - GitHub App client
  aca.py           - Azure Container Apps client
  reconciler.py    - Reconciliation engine
  cli.py           - synos CLI

examples/          - Example App/Project YAML files
docs/              - Architecture diagrams, decisions, roadmap
```

## CLI Commands

- `synos bootstrap` - Configure GitHub App and Azure credentials
- `synos operator` - Run the operator loop
- `synos sync` - Force reconciliation pass now
- `synos diff` - Show desired vs live state diff
- `synos status` - Show operator status and last sync results
