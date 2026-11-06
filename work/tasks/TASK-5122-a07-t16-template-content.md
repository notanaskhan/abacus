---
id: TASK-5122
title: "A-07-T16 template content part 2: reports, reason codes, paragraph blocks, signature placeholder"
spec: SPEC-000  # row (A-07-T16)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-07
plan_key: A-07-T16
branch: s29-a07-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
AUD-23's report templates and catalogue as content, loaded by import, not code.

## Plan
files/a07_templates.yaml only: four report bundles flow through a07_template_events to C11's import. Reason codes and blocks stay in the file until A-07-T24's import route.

## Progress log
- 2026-11-06: built. `backend/tests/unit/scenarios/test_a07t16_template_content.py` written, not run (end pass). The bundles load in a one-off read.

## Decisions made during this task
DEC-2418
