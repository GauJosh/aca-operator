# Decision Record: Go vs Python for SynosCD

Status: Accepted (Python-first)  
Date: 2026-06-08

## Decision Scope

Choose implementation language for:

1. SynosCD operator (long-running reconciler)
2. synos CLI

## Constraints

- Team preference leans Python.
- Reliability and operational simplicity are important for production GitOps behavior.
- Running inside ACA with managed identity and Azure API calls.

## Evaluation Criteria

| Criterion | Weight (1-5) | Go | Python | Notes |
|---|---:|---:|---:|---|
| Runtime footprint (CPU/RAM) | 5 | 5 | 3 | Long-running controller cost profile |
| Concurrency model for reconcile loops | 5 | 5 | 3 | Parallel sync, backoff, worker pools |
| Single-binary deployment simplicity | 4 | 5 | 2 | Packaging, startup, ops simplicity |
| Team familiarity / onboarding | 5 | 3 | 5 | Your org preference |
| Ecosystem fit for cloud controllers | 4 | 5 | 3 | Controller patterns, SDK maturity |
| Local dev velocity | 3 | 3 | 5 | Iteration speed |
| Observability + profiling ergonomics | 3 | 4 | 4 | Both good with standard tooling |
| Total weighted score |  | TBD | TBD | Fill after calibrating weights |

## Decision

- Start SynosCD with **Python** for both operator and `synos` CLI.
- Keep implementation modular so a future operator-core migration to Go is possible without changing user-facing schema.

## Operating Guardrails (Python-first)

- Use explicit worker limits for reconcile concurrency.
- Enforce idempotent apply + retry with jittered backoff.
- Track SLOs for reconcile latency, memory, and error rate from day one.
- Treat packaging and runtime reproducibility as release gates.

## Re-evaluation Triggers (switch consideration to Go)

- Sustained memory/CPU costs exceed agreed budget for target scale.
- Reconcile throughput cannot meet SLOs after optimization.
- Operational complexity (packaging/debug/startup reliability) becomes a repeated incident source.
- Team confirms long-term controller investment where Go materially reduces risk.

## Open Questions

- Is one language required across operator + CLI by platform standards?
- What are target scale expectations (apps per ACE, reconcile frequency)?
- Is cold-start/footprint a hard cost constraint?

## Review Date

- Reassess after MVP + first production pilot (or earlier if any trigger is met).
