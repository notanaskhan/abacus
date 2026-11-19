---
id: TASK-8740
title: "T-08-T11: Two-year comparison service, explanations, acceptance and export"
spec: SPEC-710
acceptance_criteria: [AC-21, AC-22, AC-24, AC-25]
risk_zone: amber
status: in-review
branch: s51q-t08-t11-two-year-service
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: T-08-T11
---

## Objective
Finish T-08-T11 (TASK-8726): TAX-10 reads the return's approved engine summary against the prior year's return of the same entity and form over the reviewed 1040 line map, with the firm's two-year variance row pinned; people write explanation versions and accept the newest over the values they saw; the comparison exports as a workbook.

## Plan (amber)
1. tax/compute/two_year_lines.py (OQ-15: a reviewed repo file; Form 1040 per TAX-10).
2. tax/two_year_service.py: comparison (walls 404; 409 threshold_unavailable without the firm's variance_thresholds tax_two_year row; comparison_unavailable without both summaries), edit_explanation (insert-only version), accept (409 explanation_stale on a moved hash or an older version; human-only CHECK), export_xlsx (safe_xlsx; audited).
3. practice_tools_contract: two-year read, explanation edit, accept and export live; explain (the agent run) stays 501 until its prompt.
4. tests/unit/tax/test_t08t11_two_year_service.py.

## Progress log
- `2026-11-19` — Built. Not built: the checklist parameter source (OQ-2: review_checklist parameters.two_year_threshold overrides the policy; the checklist payload has no parameter yet, so the policy row is used and named), citations on explanations (the agent's run writes them), and Feld's 8 flagged lines (TAX-10 seed). Gates and tests run once at the S51 end pass (build first, test last).
