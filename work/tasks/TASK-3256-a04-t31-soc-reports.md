---
id: TASK-3256
title: A-04-T31 service organizations and SOC 1 evaluation (gap by code, CUECs, drafts, reliance card)
spec: SPEC-000  # row (SPEC-620 AC7.1, AC7.2, AC7.3, AC7.4, AC7.6)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T31
branch: s27-a04-t31
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Keystone shows a 92-day gap, raising the reliance card returns 409 gap_open until the Sep 22
bridge letter is received, and the Sep 29 reliance decision is Margaret's."

## Plan (amber)
- `assurance/compute/soc_gap.py`: pure gap of the plan year the report's period leaves uncovered,
  with its engine stamp; a bridge letter marks it bridged, never shrinks it.
- `assurance/soc_reports.py` over 0657's tables: read with the gap live from the plan year
  (engagement fiscal period); `evaluate` against `row_version` (stores `gap_days` and stamp);
  `map_cuec` (Evidenced only with evidence); `request_drafts` (bridge letter or CUEC evidence as
  C5 drafts a person sends); `request_reliance` (409 `gap_open`, `cuec_evidence_missing`,
  `reliance_requested`) raising the EP's `service_org_reliance` card; its applier sets the
  reliance state and emits `service_org.reliance_concluded`.
- `planning_contract.py`: the five SOC routes go live; `SocReportPatchIn` gains
  `bridge_letter_evidence_version_id` (additive).
- Error catalogue regenerated (4 codes); client regenerated (no schema renamed).
- Tests: `tests/unit/assurance/test_a04t31_soc_reports.py`.
- Not here: SOC exception impact and routing through the exception-route slot have no route in
  the stub; the service writes them with A-04-T35's mode output (recorded as partial).

## Progress log
- 2026-11-04: built. Tests at the S27 end review.

## Decisions made during this task
DEC-2236.
