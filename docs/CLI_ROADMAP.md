# CLI Implementation Roadmap

## Current CLI Status

### Implemented Commands

**`synos operator`** - Main reconciliation loop (runs in ACA as container app)
```bash
synos operator [--interval SECONDS] [--log-level LEVEL]
```
- ✅ Polls Git for manifest changes
- ✅ Lists live Azure Container Apps state
- ✅ Detects drift (spec mismatch or health failure)
- ✅ Applies changes (create/update)
- ✅ Optional prune of removed apps
- ✅ Structured JSON logging

**`synos sync`** - One-shot synchronization
```bash
synos sync --git-repo-url URL [--github-app-id ID] [--github-app-key KEY]
```
- ✅ Fetch Git state
- ✅ Reconcile with Azure (similar to one operator pass)
- ✅ Useful for testing & debugging

### Placeholder Commands (Not Implemented Yet)

**`synos diff`** - Show desired vs live state
```bash
synos diff [--app-name NAME] [--output json|yaml]
```
**`synos status`** - Show reconciliation status
```bash
synos status [--app-name NAME] [--watch]
```
**`synos bootstrap`** - Initialize operator deployment
```bash
synos bootstrap [--subscription-id ID] [--resource-group RG]
```

---

## What It Takes to Complete the CLI

### Technical Requirements

**Architecture:**
- Built with `typer` (Python CLI framework on top of Click)
- Commands organized as separate modules in `src/synoscd/commands/`
- Shared parameter parsing & validation
- Consistent output formatting (JSON, YAML, table)

**Configuration Management:**
- Environment variables for all settings (12-part config)
- Optional `~/.synoscd/config.yaml` for defaults
- CLI flags override env vars override config file

**Authentication:**
- Azure: `DefaultAzureCredential` (local + RBAC in ACA)
- GitHub: App ID + private key for manifest repo access
- Support `SYNOSCD_*` env vars for CI/CD

### Implementation Effort Estimates

| Command | Complexity | Effort | Details |
|---------|-----------|--------|---------|
| `diff` | Low | 4-6h | Reuse existing `needs_update()` logic, pretty-print diff |
| `status` | Medium | 8-12h | Fetch live state, show provisioning state + health, add `--watch` mode |
| `bootstrap` | High | 20-30h | Create ACE, MI, role assignments, deploy operator app, configure GitHub App |
| `logs` | Medium | 6-8h | Stream from `az containerapp logs` with JSON parsing |
| `config validate` | Low | 2-4h | Validate manifest files without applying |

**Total for full v1.0 CLI: ~40-60 hours**

### High-Value Quick Wins

1. **`synos diff`** (4-6h)
   - Show what would change before applying
   - Great for UX & safety
   - Reuses existing normalization code

2. **`synos config validate`** (2-4h)
   - Dry-run manifest parsing
   - Early error detection in CI/CD

3. **`synos logs`** (6-8h)
   - Stream operator logs from Azure
   - Better than `az containerapp logs` directly

### Recommended Next Steps (Priority Order)

**Immediate (For v0.2.0):**
- ✅ Keep `operator` and `sync` as-is (working well)
- ⬜ Implement `diff` command (high value, low effort)
- ⬜ Implement `config validate` (low effort, good UX)

**Medium-term (v1.0):**
- ⬜ Implement `status` command with `--watch`
- ⬜ Implement `logs` command
- ⬜ Add config file support (`~/.synoscd/config.yaml`)

**Longer-term (v1.1+):**
- ⬜ Implement `bootstrap` command (operator deployment automation)
- ⬜ Webhook support for event-driven sync
- ⬜ `rollback` command to revert to previous state
- ⬜ `resources` command to show resource usage stats

---

## Architecture for Future CLI Expansion

### Recommended Directory Structure

```
src/synoscd/
├── cli.py                    # Main CLI entry point
├── commands/
│   ├── __init__.py
│   ├── operator.py          # synos operator - DONE
│   ├── sync.py              # synos sync - DONE
│   ├── diff.py              # synos diff - TODO
│   ├── status.py            # synos status - TODO
│   ├── logs.py              # synos logs - TODO
│   └── bootstrap.py         # synos bootstrap - TODO
├── config.py                # Settings
├── aca.py                   # ARM client
├── reconciler.py            # Reconciliation logic
└── git.py                   # Git client
```

### CLI Patterns

**Example: Implementing `synos diff`**

```python
# src/synoscd/commands/diff.py
@app.command()
def diff(
    app_name: Optional[str] = typer.Option(None, help="Show diff for specific app"),
    output_format: str = typer.Option("text", help="text | json | yaml"),
    dry_run: bool = typer.Option(False, help="Show what would be reconciled"),
):
    """Show desired state vs live Azure state."""
    config = SynoscdConfig()
    reconciler = Reconciler(config)
    
    # Fetch desired from Git
    desired_apps = await reconciler.fetch_git_apps()
    
    # Fetch live from Azure
    live_apps = await aca.list_apps()
    
    # Compute diff for each app
    for app_name_key in desired_apps.keys():
        if app_name and app_name_key != app_name:
            continue
        
        desired = desired_apps[app_name_key]
        live = live_apps.get(app_name_key)
        
        diff = reconciler._compute_diff(desired, live)
        print_diff(diff, format=output_format)
```

### Output Formatting Templates

All commands should support:
- **Text** (default): Human-readable table/tree format
- **JSON**: For scripting/automation
- **YAML**: For manual review/editing

```python
# src/synoscd/format.py
def format_output(data, format_type: str. = "text"):
    if format_type == "json":
        return json.dumps(data, indent=2)
    elif format_type == "yaml":
        return yaml.dump(data, default_flow_style=False)
    else:
        return format_as_table(data)  # custom table formatter
```

---

## Testing Strategy for CLI

### Unit Tests
- Mock `Reconciler` and `ACA` for fast feedback
- Test arg parsing and validation
- Test output formatting

### Integration Tests (Manual)
```bash
# Test diff command
synos diff --app-name demo-app --output json

# Test status command  
synos status --watch

# Test against real Azure/Git
./tests/integration/e2e-test.sh
```

### Load Testing (Optional)
- Sync 100+ apps to monitor performance
- Measure reconciliation time per app

---

## Summary: CLI Maturity Timeline

| Version | Focus | Timeline |
|---------|-------|----------|
| v0.1.0 (Current) | Core operator + sync | ✅ Done |
| v0.2.0 | `diff`, `status`, `logs` | 3-4 weeks |
| v1.0.0 | `bootstrap`, config file, Helm chart | 8-12 weeks |
| v1.1.0 | `rollback`, `resources`, webhooks | Future |

Your current v0.1.0 is **production-ready** for core use case (automated sync). Additional CLI commands are **nice-to-have enhancements**, not blockers for adoption.
