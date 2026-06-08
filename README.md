# SynosCD

GitOps-style operator concept for Azure Container Apps (ACA) running inside an ACA Environment (ACE).

## Current Status

This repository is currently in **design/discovery** mode.

- No implementation code yet.
- Architecture and decisions are being drafted first.
- Goal: choose language/runtime and define control-plane contract before coding.

## Initial Artifacts

- `docs/architecture/synoscd-context.mmd` – editable Mermaid architecture diagram.
- `docs/decisions/go-vs-python.md` – language decision matrix and recommendation criteria.
- `docs/roadmap.md` – phased plan from design to MVP.

## Working Name

- Operator: **SynosCD**
- CLI: **synos**

## Decision Guidance (short)

- If long-running reconciler reliability, low footprint, and operational simplicity dominate: prefer **Go**.
- If team velocity and talent alignment dominate and you can accept higher runtime overhead: **Python** is viable.

See detailed tradeoffs in `docs/decisions/go-vs-python.md`.
