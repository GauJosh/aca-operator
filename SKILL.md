# SKILL.md

## Project Identity

- Project: **SynosCD**
- Operator name: **SynosCD**
- CLI name: **synos**
- Goal: GitOps-style reconciliation for Azure Container Apps (ACA) inside an ACA Environment (ACE).

## Current Stage

- Repository is in **design/discovery** phase.
- Do **not** assume implementation code exists.
- Prefer discussion artifacts (docs, diagrams, decisions) before code.

## Architecture Boundaries

- Terraform + `az` CLI own foundation/bootstrap (ACE and base platform resources).
- SynosCD owns ACA app-level reconciliation only.
- SynosCD should only manage explicitly labeled/owned resources.

## Language Decision

- **Python-first** for now (operator + CLI) to align with team preference.
- Keep design modular so operator core can migrate to Go later if needed.
- Re-evaluate for Go if operational or scale triggers are hit.

## GitOps Behavior Expectations

- Git is source of truth.
- Pull-based reconcile loop from GitHub App auth.
- Webhook-triggered sync + periodic full reconciliation.
- Idempotent apply, retries with backoff, and drift detection required.

## Schema Direction

- Use Kubernetes-style configuration shape (`apiVersion`, `kind`, `metadata`, `spec`, `status`).
- This is a product contract style, not a Kubernetes API server dependency.

## Working Conventions for Agent

- Prefer minimal, focused changes.
- Keep docs and diagrams in sync with decisions.
- If a decision changes, update decision docs before proposing code.
- Ask clarifying questions only when needed; otherwise proceed.

## Key Docs

- `README.md`
- `docs/architecture/synoscd-context.mmd`
- `docs/decisions/go-vs-python.md`
- `docs/roadmap.md`
