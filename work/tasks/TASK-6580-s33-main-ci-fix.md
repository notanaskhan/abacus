---
id: TASK-6580
title: "S33 main CI fix: stage-1 pyright, stage-2 contract and worker inventories, two integration tests"
spec: SPEC-646  # R-02 contracts (C10, C18) among the suites repaired
acceptance_criteria: [AC-1]  # main's CI green again
risk_zone: amber
status: in-review
branch: s33-ci-fix
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-10
updated: 2026-11-10
plan_key: Q-03-T221
---

## Objective
Main's CI has been red since c490cfae2: stage 1 (pyright), stage 2 schema and api-client
(contract inventories), unit (worker) and two integration tests.

## Build
- Stage 1: `tests/security/test_classification_scrubbing.py` and the journal test import
  `from importlib.util import …` (pyright reported `import importlib.util` unused in CI only).
- Contracts brought to what S33 shipped, keeping each test's intent:
  - C10: the six live deliverables routes no longer document 501; the stubs still do (DEC-3136).
  - C18: `uncorrected_misstatements` is registered (R-02-T15); the package route checks
    `portal.approvals` first, so the test turns it on to reach the 409 slot (DEC-3112).
  - C16: the relay also subscribes `/v1/events`'s invalidating events (DEC-3117).
  - Audit completion: 60 operations (A-07-T32's readiness check, DEC-3109).
  - Audit log AC-8: the engagement activity CSV export (POST) and AUD-29's query (POST, a read
    under `audit_event.read_engagement`) are not changes to an event (P-05-T11).
- Worker: the routing inventory lists `client_approval.requested` (DEC-3140).
- Integration:
  - `kernel.dispatch.signal_workflow` is best effort as documented: an unconfigured Temporal
    (`RuntimeError`) or a refused connection (`OSError`) skips the signal (the notices
    stale-edit test's 500).
  - The canary relay test drains in larger passes; the shared test database outgrew 20
    default passes.
- Tests: `tests/unit/kernel/test_s33_signal_best_effort.py`.

## Progress log
- `2026-11-10` — Local: contracts, worker, kernel and the touched tests pass (9,440). The two
  integration fixes are confirmed only by CI (no database here).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3180 | `signal_workflow` treats an unconfigured or unreachable Temporal as "service down" | no |
