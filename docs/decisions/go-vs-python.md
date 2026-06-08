# Decision Record: Go vs Python for SynosCD

Status: Draft  
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

## Recommendation Shape

- **Default recommendation:** Go for operator core.
- **Pragmatic option:** Python for CLI and auxiliary tooling if that aligns with team skills.
- **Alternative if Python-first mandate:** Build operator in Python with stricter guardrails:
  - explicit worker limits
  - robust retry/idempotency strategy
  - memory/latency SLOs and load tests early

## Open Questions

- Is one language required across operator + CLI by platform standards?
- What are target scale expectations (apps per ACE, reconcile frequency)?
- Is cold-start/footprint a hard cost constraint?
