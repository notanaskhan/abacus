---
id: TASK-1739
title: A-02-T30 Live ledger pipeline wiring (on-demand pulls)
spec: SPEC-333
acceptance_criteria: [AC-46]
risk_zone: red
status: in-review
epic: A-02
plan_key: A-02-T30
branch: s14-a02-t30
created: 2026-10-28
updated: 2026-10-28
---

## Objective
On-demand pulls through a live ledger. Acceptance (backlog row): "Simone Baptiste's pull against
the QBO sandbox on staging records an on_demand sync run and a snapshot AUD-06 can adopt, and every
earlier retrieval history still replays."

## Plan (red)
- `connections/pulls.py` (`pull`), exported as `connections.api.pull_ledger`; the integrations
  route live (Idempotency-Key); `pipeline.finish_at_snapshot`, its activity and the workflow's
  `on-demand-pulls` patch; C20 stub test marks the route live. DEC-829.
- Rollback: flag `connections.live_ledger` off; revert (the patch is additive).

## Acceptance
| Check | Test |
|---|---|
| One on_demand run, labelled, no request item, audited, workflow started | `backend/tests/integration/backfill/test_a02t30_ledger_pulls.py::test_ac_a_pull_records_one_on_demand_run` |
| Earlier histories replay | `backend/tests/workflows/test_retrieval_replay.py` (batch review) |
| Repeat, no ledger, reauth, flag off, staff refused | five tests |

## Progress log
- `2026-10-28` — Built. ruff, pyright, lint-imports, banned patterns clean; `make regenerate`.
  Tests written, not run (end-of-batch review); the v3 history is recorded there.

## Handoff
- **Current state:** PR open, held for the batch.
- **Next:** N-01-T10.
