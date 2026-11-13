---
id: TASK-7703
title: T-05-T42 Section sign-offs and post-run tie-outs
plan_key: T-05-T42
spec: SPEC-651
acceptance_criteria: [AC-F7, AC-F8]  # section sign-offs refuse while a tie-out is off; self-check issues resolve by the system
risk_zone: amber
status: in-review
branch: t05-t42-sections-tie-outs
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Sections of the entity workbook as sign-off targets with computed staleness, the `tie_out_off`
precheck with a sealed note, and the tie-outs after every run as issues linked to their cells.

## Plan (amber)
- Migration 0860 (on 0851): `tax_workbook_sections`, `tax_section_acknowledgements` (both
  insert-only, forced RLS), `issues_system_resolved_dependency` widened to `self_check`.
- Files: `tax/entity_sections.py` (new), `tax/workbook_contract.py` (sections and sign-off routes),
  `tax/api.py` (registration, subscription), `tax/registry.py`, `tax/audit_targets.py`,
  `review/issues.py` (`record_self_check_issue`, `IssueSource`), `review/issue_resolutions.py`
  (`system_resolve_self_checks`), `review/api.py`, `agents/engagement_run.py` + `agents/api.py`
  (`run_work_item_ref`), `audit_trail/activity_reviewed.py`, contract notes.
- Tests: `backend/tests/unit/tax/test_t05t42_sections_tie_outs.py`.
- Rollback: revert the PR and downgrade 0860 (refused while a self-check issue is
  `system_resolved_only`; resolve those first).

## Partial
- Cell addresses in links follow this workbook's layout (05 F, 07 B9), not the handoff's
  H8:H12, J13 and J15 (TXP-11's sheet layout differs; reconciled at T-05-T46's freeze).
- Schedule L line 21 is not a workbook cell: `item_l_m2` compares the partners' ending capital
  (Item L) with M-2 line 9.
- The note is sealed and hashed; no screen reads it back yet (TXP-07's sign-off history, T-05-T43
  family of screens).

## Progress log
- 2026-11-13: built; tests written, not run (S41 end pass). OpenAPI export clean.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4705 | sections, the precheck and the sealed note | no |
| DEC-4706 | tie-outs as system self-check issues; review additive and 0860 | no |
