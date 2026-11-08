---
id: TASK-6214
title: A-05-T58 EBP-07 Form 5500 tie-out and supplemental schedules
spec: SPEC-640
acceptance_criteria: [AC-1]  # typed values in the form ink; one match id lights row and field; empty until the draft
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T58
branch: s31-a05-t58
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan
- Service read `assurance/ebp_form5500.form5500_view`: the current (not superseded) draft, its
  lines and Part IV answers (`evidence_ref.basis`); no draft reads empty.
- Contract, additive (`assurance/ebp_contract.py`): `Form5500RowOut`; `Form5500Out.rows`,
  `draft_id`, `evidence_version_id`. The route replaces its hard-coded example; each row's
  `match_id` comes from its citation (`evidence.api.citation_display`).
- Screen `apps/web/src/screens/EBP-07/` (`useForm5500Canvas`, copy verbatim from the handoff):
  Schedule H with tallies, Note 8 chips and the reconciliation note; Part IV with evidence links
  and the inconsistent flag with "Raise exception…"; Schedules (4i, 4a); the empty state with
  "Remind Summit"; C-20 off. Composed in AUD-02 as `ebp_07`; "Source Docs" opens the draft PDF in
  the viewer dock.
- Fixtures `fixtures/seed/ebp07.ts`, scenarios a–e and off; tests `EBP-07.test.tsx` and
  `tests/unit/assurance/test_a05t58_form5500_read.py` (run at the S31 end pass).

## Partial (DV-EBP-07-2 to 4)
- Part IV lists the contract's five lines; the 4i schedule lacks party-in-interest, description
  and cost columns until a 4i render read exists; Send note (A-06), Remind (POR-14 route) and
  keyed values (T38) stay stubs.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2814 | Stored tie-out on the read; the citation's match id lights row and field | no |

## Progress log
- 2026-11-08: built; tests written, run at the S31 end pass.
