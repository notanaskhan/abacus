---
id: TASK-1474
title: Independent AC tests for the AUD-06 read model, ties and reviewable, plus the AUD-06 authz review (A-02-T21)
spec: SPEC-333
acceptance_criteria: [AC-5, AC-9, AC-10, AC-11, AC-12, AC-13, AC-17, AC-28]
risk_zone: amber
status: in-progress
epic: A-02
plan_key: A-02-T21
branch: s12-ledger
created: 2026-10-27
updated: 2026-10-27
test_author: ayushkbhatia
test_session: 2026-10-27, s12-ledger (ADR-078 separate test session; did not write A-02-T10 or A-02-T17)
---

## Objective
"The suite covers walls, independence, agent refusal and tie goldens, and the authz review note
is merged before Tue Jun 1, 2027."

## Plan
Tests only, from SPEC-333 AC-5, AC-9 to AC-13, AC-17, AC-28, the A-02 epic §3.2 and §3.3, C9 v1
§2 and §6, the assurance and workpapers matrix rows and `error-codes.yaml`.

- `backend/tests/integration/backfill/test_a02t21_aud06_ties_independent.py` (shares
  `tb_support.py` with TASK-1473): walls 404 identical to a missing engagement on every TB route,
  another firm 404, off-team and client users refused, `independence_pending`, the agent refused
  every C9 action and `sign_off.prepare`, the human-only and cited CHECKs on check versions,
  server figures, `allowed_actions` per role, `newer_snapshots`, the tie goldens (rollforward
  312,400.00; BrokerWindow off 1,560.00 with its line flag), results computed on read,
  `citation_required`, a citation of another engagement, define and edit audited with a stale
  version refused, the issue link (`Idempotency-Key` required, replayed, reuse refused, set once,
  another engagement's issue 404, stale 409, extra fields and reviewers refused), and "Changed
  after sign-off" with no sign-off row updated.
- The authz review note of the AUD-06 routes (below).

Rollback: delete the file.

## Progress log
- 2026-10-27: suite written (build first).
