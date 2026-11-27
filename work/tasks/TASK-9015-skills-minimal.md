---
id: TASK-9015
title: "K-03-T21: Minimal skills import and reads"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-k03-t21-skills
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: K-03-T21
---

## Objective
Row acceptance: Importing BH-SK-430 v1 and v2 needs skill.import with fresh MFA, unsafe markdown is refused, and a pin to a draft skill version shows the KNW-06c warning without blocking publish.

## Done
- import endpoint with fresh MFA and immutable versions
- sanitised-markdown schema (refuse, never strip)
- skills and skill-version reads
- draft-pin warning read
- published body for runs
- Postgres acceptance and schema tests

## Progress log
- `2026-11-26` — 9 tests pass on Postgres. Also moved T20 test literals the secrets scan flagged.
