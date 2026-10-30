---
id: TASK-5009
title: "Account mapping: prior-year match, tallies and the confirm event"
spec: SPEC-316
acceptance_criteria: [AC-8]
risk_zone: amber
status: done
branch: task-5009-mapping-confirm
worktree: agentwt
created: 2026-10-26
updated: 2026-10-30
---

## Plan keys
A-03-T08 (partial: the prior-year rule, tallies, TB balanced, confirm event).

## Plan
- **`ledger/mapping.py`:**
  - `resolve_line` (pure): edit, then prior year (normalised code to FS-line key), then the ranges, else unmapped;
  - `normalised_code` and `prior_keys`;
  - `MappingView` gains `prior_year`, `number_range`, `tb_balanced` and `fs_line_keys`;
  - `statements_for` takes `prior`.
- **`engagements`:** `prior_engagement_of(tenant, id)` (SPEC-025 `prior_engagement_id`).
- **`assurance/mapping.py`:** `mapping_with_prior` is used by the view, statements, sign-offs, facts, reviewables and the dashboard, so the content hash is the same everywhere. The L1 sign-off records `mapping_set.confirmed`.
- **Web:** TbMapping shows "Prior year", the tallies, and an out-of-balance pill.
- **Rollback:** revert the PR. There are no migrations.

## Notes
- Only FS-line keys cross from the prior engagement, never figures. Matching by key rather than id lets a new grouping-set version still match.
- `TbMappingWorkflow`, tallies' subtotal-off and staleness (A-03-T14) are not built.

## Progress log
- test_mapping (9, 3 new) and spec316mapping (5) pass.

## Definition of done
- [x] Targeted tests pass.
- [x] check-fast passes.
