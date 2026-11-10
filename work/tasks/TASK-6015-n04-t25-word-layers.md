---
id: TASK-6015
title: "N-04-T25 the extract cases' word layers, so a real run reads every case"
spec: SPEC-000  # row (N-04-T25)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T25
branch: s29m-n04-t25-layers
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-08
updated: 2026-11-08
---

## Objective
A real run skipped every extract case (no word layer) and failed its report on `extract_cases_without_lines`. Give each of the 12 extract cases a synthetic word layer that matches its labels.

## Plan
evals/notices_responder/suite.yaml: `document_lines` on each extract case (agency and notice number, amount due, respond-by), refs D1:p1 to p3, the fake answers' citations among them; degraded scans garble the respond-by date with OCR confusions. Thresholds and labels unchanged. Test test_n04t25_word_layers.py. test_n04t25_clearance.py imports organisations.api so it collects on its own. Shadow plan: the extract labels join the CPA label review. Rollback: revert.

## Progress log
- 2026-11-08: built. test_n04t25_word_layers (4), test_n04t25_clearance (12, now also alone), test_n04t18 (9) pass; ruff, pyright clean.

## Decisions made during this task
DEC-2611
