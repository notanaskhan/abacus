---
id: TASK-2629
title: N-02-T47 signatures hardening (mutation scope, p95 surge profile, provider rate-limit backoff)
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T47
branch: s21-n02-t47
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"mutmut reports at least 75 percent on modules/signatures and the surge profile drains within the
hour." (ADR-079; N-02 §5.6.)

## Plan (red)
- Files: `signatures/provider.py` (`ProviderRateLimited`, `retry_after_seconds`),
  `signatures/docuseal.py` (429 → `ProviderRateLimited`), `signatures/activities.py`
  (`_honour_rate_limit` around every provider call: send, status, void, completed),
  `abacus_tools/loadtest/{scenario,run,journey_vars}.py` (per-request Idempotency-Key, the E18 var),
  `loadtest/scenarios/signing_surge.yaml`, `abacus_tools/quality/mutation.py` and
  `backend/mutation-thresholds.yaml` (`signatures` scope, floor 0), the load-test runbook row.
- No migration, no flag, no registry change. Rollback: revert the commit; Temporal retries fall
  back to the policy's own backoff.
- Tests: `tests/unit/signatures/test_n02t47_rate_limit_backoff.py`.

## Scope and deviations (DEC-1673)
- The 75 percent floor is the target, not yet the floor: `signatures` enters at 0 and is raised to
  its first weekly baseline; survivor triage runs on that report.
- The surge profile times send under load through one draft (E18); distinct drafts per send are
  Q-03-T131's tax surge content. The drain-in-the-hour reading is the perf stack's (Q-03-T036).

## Progress log
- 2026-11-01: built; tests and a security review at the batch's end review.
