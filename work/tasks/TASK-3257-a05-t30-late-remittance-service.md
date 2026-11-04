---
id: TASK-3257
title: A-05-T30 late-remittance service and EBP-04 routes
spec: SPEC-000  # row (SPEC-640 AC-30)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T30
branch: s27-a05-t30
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Recording the Sep 30 correction changes EBP-04f, the 4a preview and the AUD-27 PT card
together, from one row."

## Plan (amber)
- `assurance/ebp_remittances.py` over 0658: `late_remittances` (exported as
  `assurance.api.late_remittances` for AUD-27 and EBP-07), `schedule_h_4a`, `reconciliation`
  (receivable at year end from the payroll register), `record_correction` (evidence required;
  `found` → `pending_vfcp_scc` → `corrected`; Form 5330 `exposure` → `not_required_pte_2002_51`
  or `filed`; one insert-only human event; audited).
- `ebp_contract.py`: reconciliation and late remittances read live; `GET …/ebp/schedule-h-4a`
  (new, the 4a preview); the correction route live.
- Error catalogue (2 codes) and client regenerated.
- Tests: `tests/unit/assurance/test_a05t30_late_remittances.py`.
- Partial: AJE-1's status from C8 and F-1 from AUD-15 are joined by the EBP-04 screen task
  (A-05-T31) through their own APIs; the 4a schedule's C11 render is `ebp_schedule.render`'s.

## Progress log
- 2026-11-04: built. `make generate` caught `Mapped[list[UUID]]` without a column type: the
  event's `evidence_version_ids` maps `ARRAY(UUID)`.

## Decisions made during this task
DEC-2237.
