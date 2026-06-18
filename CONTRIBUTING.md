# Contributing to SynosCD

Thank you for your interest in contributing to SynosCD! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and constructive in all interactions.

## Getting Started

### Prerequisites
- Python 3.9+
- Git
- Azure CLI (`az`) for local testing
- Podman or Docker (for building container images)

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/aca-operator.git
   cd aca-operator
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # Windows
   # or
   source venv/bin/activate      # macOS/Linux
   ```

3. **Install development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify setup:**
   ```bash
   synos --help
   pytest tests/
   ```

## Making Changes

### Code Style
- **Formatting**: We use `black` for code formatting
  ```bash
  black src/ tests/
  ```
- **Linting**: We use `ruff` for linting
  ```bash
  ruff check src/ tests/
  ```
- **Type Checking**: We use `mypy` for Python type hints
  ```bash
  mypy src/
  ```

### Before Committing
Run the full validation suite:
```bash
ruff check src/ tests/
black --check src/ tests/
mypy src/
pytest tests/ -v
```

### Testing
- Add tests for any new functionality in `tests/`
- Use `pytest` for test execution
- Aim for meaningful test coverage:
  ```bash
  pytest tests/ -v --tb=short
  ```

## Submitting a Pull Request

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code style guidelines above

3. **Commit with clear messages:**
   ```bash
   git commit -m "feat: add new feature" -m "Detailed description of changes"
   ```
   Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`

4. **Push and open a PR:**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a Pull Request on GitHub

5. **Address review feedback** - maintainers will review your PR

## What We're Looking For

### High-Priority Contributions
- Bug fixes with test cases
- Documentation improvements  
- Performance optimizations
- New reconciliation features (e.g., webhook triggers, multi-repo support)
- Integration tests for real Azure environments

### Planned Features (Good First Issues)
- `synos diff` - Compare Git desired state vs live Azure state
- `synos status` - Show reconciliation status for all apps
- Webhook-triggered sync (event-driven reconciliation)
- Secrets integration with Azure Key Vault
- Helm chart for operator deployment

## Architecture Overview

```
┌─────────────────┐
│  Git Repository │ (Source of Truth)
│  (YAML Manifests)
└────────┬────────┘
         │
    ┌────▼─────────────┐
    │  SynosCD Operator│ (Pull-based Reconciliation)
    │  - Fetch Git     │
    │  - List Azure    │
    │  - Diff & Apply  │
    │  - Health Check  │
    └────┬──────────────┘
         │
    ┌────▼────────────────────┐
    │ Azure Container Apps API │ (ARM v2024-03-01)
    │ - App Create/Update      │
    │ - App Delete/Prune       │
    │ - State Polling          │
    └─────────────────────────┘
```

### Key Components

- **config.py**: Environment configuration & settings
- **aca.py**: Azure Container Apps ARM client (real API operations)
- **reconciler.py**: Main reconciliation loop with drift detection & health checking
- **cli.py**: CLI entry point (`synos` command)

## Testing Strategy

### Unit Tests
Located in `tests/`: Validate configuration parsing, spec normalization, safety logic

### Integration Tests (Manual)
- **Local dev**: Use `az login` + DefaultAzureCredential
- **Production**: Deploy to ACA with managed identity, verify real reconciliation

### Security Scans
- Bandit for Python security issues
- CodeQL for dependency vulnerabilities
- Automated on all PRs via GitHub Actions

## Documentation

- **README.md**: User-facing guide (features, quickstart, troubleshooting)
- **DEPLOYMENT.md**: Detailed operator deployment steps
- **This file (CONTRIBUTING.md)**: Developer guide
- **Inline comments**: Complex reconciliation logic is well-commented

## Release Process

1. **Update version** in `pyproject.toml`
2. **Create PR** with changelog
3. **Merge to main** - triggers GitHub Actions workflow
4. **Workflow automatically**:
   - Runs lint, test, security scan
   - Builds & pushes container image to GHCR
   - Creates git tag (v0.1.0, v0.2.0, etc.)
   - Publishes GitHub Release

## Debugging Tips

### View operator logs
```bash
# Local
synos operator --log-level debug

# Azure
az containerapp logs show --name synoscd-operator --resource-group YOUR_RG --follow
```

### Check live Azure state
```bash
az containerapp show --name demo-app --resource-group YOUR_RG
az containerapp environment list --resource-group YOUR_RG --query "[].{name:name, location:location}"
```

### View Git reconciliation state
```bash
synos sync --git-repo-url https://github.com/YOUR/REPO --github-app-id YOUR_APP_ID --dry-run
```

## Questions?

- Search [existing issues](../../issues) first
- Open a [new issue](../../issues/new) with details about what you're trying to do
- Tag with: `question`, `bug`, `enhancement`, or `documentation`

Happy contributing! 🚀
