---
id: TASK-6119
title: "A-06-T33 independent tests for the FS render and client sends"
spec: SPEC-000  # row (A-06-T33)
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: A-06
plan_key: A-06-T33
branch: s30-a06-t33
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
ADR-078 tests for A-06-T29: deny-all fetcher inherited, watermark and AR-C 70 legend rules, grant consumed once, record-mode evidence required, client approval only by the approver of record, XLSX formula-injection escaping.

## Plan
- `tests/unit/reporting/test_a06t33_fs_render_independent.py`: the renderer's asset fetcher refuses remote, metadata, file, data and unregistered asset URLs and serves its own; DRAFT on drafts, nothing on finals; the AR-C 70 legend only for a preparation engagement; the composed body carries code's figures and no checklist, citation, agent, materiality or source words; the `fs_draft` decider rule is owner or approver of record only; XLSX text never begins a formula.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean.

## Decisions made during this task
None.
