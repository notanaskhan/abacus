---
id: TASK-8735
title: "C-02-T21: Package commentary from accepted flux and the commentary edit"
spec: SPEC-701
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
branch: s51p-c02-t21-commentary
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: C-02-T21
---

## Objective
Finish C-02-T21 (TASK-8706): the package read carries commentary — the person's text once written, otherwise filled by code from the close's accepted flux explanations (drafts never) — and PATCH …/package/commentary writes a new insert-only version with only the commentary changed.

## Plan (amber)
1. closes/flux.accepted_flux (newest set, newest explanation accepted, line order).
2. closes/package_service: drafted_commentary (compute.commentary over accepted lines), edit_commentary (new version copying the current structure, figures and hash; 409 stale_version / package_released); edit_package carries commentary forward; get_package returns commentary when the section is on.
3. delivery_contract commentary_route live; activity_reviewed close_package.commentary_edited.
4. tests/unit/closes/test_c02t21_commentary.py.

## Progress log
- `2026-11-19` — Built. Not built: the firm's own commentary template (content through C-02-T28's admin import; until then the accepted lines stand alone), and the C9 CAS catalogue ordering (the grouping set's own order is kept). Gates and tests run once at the S51 end pass (build first, test last).
