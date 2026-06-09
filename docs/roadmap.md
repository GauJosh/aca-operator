# SynosCD Roadmap (Design-First)

## Phase 0 — Discovery

- Language decision complete: Python-first (with Go re-evaluation triggers).
- Define ownership boundaries (Terraform vs SynosCD).
- Agree minimum schema for desired state.

## Phase 1 — Contract

- Draft CRD-like YAML schema (`apiVersion`, `kind`, `metadata`, `spec`, `status`).
- Define status conditions and error taxonomy.
- Define policy checks and managed-resource labeling strategy.

## Phase 2 — MVP Reconciler

- Pull desired state from GitHub App auth.
- Diff desired vs live ACA resources.
- Idempotent apply with retries/backoff.
- Webhook-triggered sync + periodic full reconcile.

## Phase 3 — Safety and Ops

- Metrics, structured logs, tracing.
- Drift reporting and alert integration.
- Rollback and suspend/resume behavior.

## Phase 4 — Scale and Multi-Env

- Multi-project/repo support.
- Promotion flow across environments.
- Rate-limit and API quota hardening.
