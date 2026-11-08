---
id: TASK-6205
title: R-02-T09 C10 registry service
spec: SPEC-646
acceptance_criteria: [AC-17, AC-18, AC-19, AC-20, AC-26]
risk_zone: amber
status: in-review
epic: R-02
plan_key: R-02-T09
branch: s31-r02-t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Objective
The C10 service behind R-02-T02's stub: publish, supersede, withdraw, the work item's delivery
state, the portal rail and FIL-01's Deliverables folder.

## Plan (amber)
- `reporting/deliverables.py`: SQL over 0710's tables in the provider's unit of work; draft
  refused without a C11 draft-mode render; idempotent per (source, evidence version); `published`,
  `superseded`, `withdrawn` events (sealed note); audit events and outbox events (`events.py`).
- `portal_deliverables(ctx, client_ids)`: C10's reader rule (`first_covering_grant`, now public in
  `deliverable_reads.py`), bands by work item, slots for K-1s, envelopes and Coming next.
- `evidence.files.register_folder_provider` slot; reporting registers `deliverables`.
- `tax.k1_portal.deliverable_k1_rows`, registered by `tax.api`.
- Audit actions reviewed; contract doc §9.
- Tests: `tests/integration/backfill/test_r02t09_c10_service.py`,
  `tests/unit/reporting/test_r02t09_portal_rail.py` (run at the end pass).
- Rollback: revert; no migration (0710 has the tables).

## Partial
- Coming next is empty: C1 has no client-visible milestone to register (R-02 AC-21's second half).
- Envelope rows wait on A-07-T24's C7 sends (registered there).
- The portal routes stay 501 until R-02-T14 (by the row).

## Progress log
- `2026-11-08` — Built; pyright clean.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2805 | Slots for rows other modules own; folder provider; status words | no |
