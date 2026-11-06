---
id: TASK-5119
title: A-07-T15 gate providers G6 to G9 by release mode, per-type policy, C13 kinds
spec: SPEC-000  # row (A-07-T15)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-07
plan_key: A-07-T15
branch: s29-a07-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
G6 to G9 in assurance/gates.py: external firms unchanged, in_app work items read live blockers from A-07's tables, and what waits on a person reaches Home.

## Plan
assurance/gates.py; engagements.engagement_type_of; six C13 gate sources; review C13_EVENTS. Rollback: revert; every firm is external today.

## Progress log
- 2026-11-06: built. `backend/tests/unit/assurance/test_a07t15_gate_providers.py` written, not run (end pass). Pyright and banned patterns on touched files.

## Decisions made during this task
DEC-2415
