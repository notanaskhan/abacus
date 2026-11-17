---
id: TASK-8401
title: "A-08-T22: SSARS workspace service"
spec: SPEC-657
acceptance_criteria: [AC-8.1, AC-8.2, AC-8.3, AC-8.4, AC-8.5, AC-8.6]
risk_zone: amber
status: in-review
branch: a08-t22-ssars-workspace
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T22
---

## Objective
Spec section: docs/plan/epics/A-08.md §3 F8. SSARS workspace service: mode projection from engagement type, rail per mode, ssars_review analytics with expectations and the firm variance policy, inquiry program from methodology content to a questionnaire with publish and templated reminders, compilation 'Read the FS' procedure with L1, preparation no-report rule and POR-08 approval row.

## Plan (amber)
1. Migration `0941_ssars_workspace.py` on 0940: workpaper kind `ssars_read_fs`; `ssars_inquiry_programs` (questionnaire per recipient, published once). F-03 already has the `preparation` engagement type (0069), so no type swap.
2. `assurance/ssars.py`: mode and standard, rail rows, inquiry summary (answered when any recipient answered), build / publish / remind, Read-the-FS working paper, C18 approval label, firm settings `ssars_variance_pct` / `ssars_variance_amount`, `review_threshold`, `put_expectation`, `require_report_allowed`.
3. Routes in `analytics_contract.py` (workspace, inquiries, publish, remind, expectation; new `POST …/ssars/read-fs`); `analytics.run` accepts `ssars_review`; `report_builder.set_choice` 409 `no_report_for_preparation`; `workpapers.api.workpapers_for` and `methodology.api.program_steps` exported; registry; error codes.
4. Tests: `tests/unit/assurance/test_a08t22_ssars.py`. Rollback: `alembic downgrade 0940`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5401). Lint and pyright clean; the app imports. Partial: the FS row's state reads `not_started` (no SSARS FS-package status is joined yet); AUD-23 compilation mode is the existing report builder's `compilation` kind; the Lakeshore '11 of 14' reading needs the Brightwater Hale/Lakeshore seed (fixtures carry it); integration tests for publish and the 409 run at the end pass. Gates and tests run once at the S48 end pass (build first, test last).
