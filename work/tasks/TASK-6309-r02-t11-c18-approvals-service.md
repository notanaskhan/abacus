---
id: TASK-6309
title: R-02-T11 C18 approvals service, decider rule, proposed_entry and fs_draft providers
spec: SPEC-646  # AC-1 to AC-7
acceptance_criteria: [AC-1, AC-2, AC-4, AC-5, AC-6]
risk_zone: amber
status: in-progress
epic: R-02
plan_key: R-02-T11
branch: s32-r02-t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
C18 live: list, detail and decide composed from registered kinds, with the decider rule, live
client human, MFA time, Idempotency-Key, seen-hash binding and attribution.

## Plan
- `engagements/client_approvals.py`: `ApprovalScope`, `scope_covered`, `covering_grant`,
  `decider_for`, `Decider` (exported).
- New `portal/approvals.py` (CLIENT-DECISION-001's file): `approvals`, `approval`, `decide`,
  `live_client_human`.
- `portal/approvals_contract.py`: list, detail, entry decide, acknowledge, package decide live;
  questions and journal stay 501.
- New `adjustments/client_approvals.py` (`ProposedEntryApprovals`, `apply_client_decision`),
  `decisions.decision_hooks()`; registered in `adjustments/api.py`.
- New `reporting/client_approvals.py` (`FsDraftApprovals`); registered in `reporting/api.py`.
- Contract §5; DEC-3009. No migration (0643 and 0660 already allow the portal channel).
- Tests: `tests/unit/portal/test_r02t11_approvals_service.py`; C18 stub test evolved (two kinds
  registered, decide routes no longer 501).
- Rollback: revert; the `portal.approvals` flag (R-02-T14) keeps POR-08 dark meanwhile.

## Progress log
- `2026-11-09` — Built; ruff and pyright clean; tests written, not run (end pass). Partial: the
  list reads items per grant scope id, so a grant on a client (not its engagement or work item)
  lists none until providers list by client; the period `contexts` stay empty until C-02; no
  integration test seeds Dana's grant and AJE-1's send yet (end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3009 | Check order, decider rule, the two providers' seen hashes and rows | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status partial.
- `2026-11-09` — Partials round (branch s32p-r02-t11, DEC-3025): client and entity grants list
  the items on their engagements (new `engagements.api.engagements_of_client`, list-exempt as a
  candidate set); unit test for the expansion; DB-backed service test
  `tests/integration/backfill/test_r02t11_portal_approvals_live.py` (AJE-1 sent, Dana's accept,
  client grant, no grant). Still open: period contexts (C-02).
