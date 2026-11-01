---
id: TASK-2816
title: Main CI triage after the S23 merge
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: amber
status: in-review
branch: s23-ci-fix
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Goal

Main's CI has been red since before the S23 batch (122fae88c) and stayed red through it
(530eab170): stage 1 stopped on a formatting error, and every integration shard failed. Make the
gates, the unit suite and the failing integration files pass on main without weakening a test.

## Plan

- Stage 1: the S23 formatting error; banned patterns, register ids and secrets-scan findings.
- Unit and integration: bring every inventory test up to the routes, workflows, schedules,
  subscriptions, audit actions, target kinds, status codes and update columns that landed.
- Boundaries (T08): signatures off audit_trail, tax off practice, by registration.
- Migration 0612: A-05's sealed EIN columns under the `tin_*` names.
- Fixture export: stable ids for server-made standards so E0 is byte-identical run to run.
- Rollback: revert the PR; 0612 downgrades by renaming the columns back.

## Decisions made during this task

DEC-1865.

## Progress log

- `2026-11-01` — failures collected from runs 41246875286, 41255139625 and 41255976428 and
  reproduced on main 328696038; fixed as DEC-1865 records. Seven status fields of other lanes are
  recorded as F-03-T10 findings for their owners, not fixed here.
- `2026-11-01` — second round from the full suites: backend unit, property, acceptance, connectors,
  contracts and workflows (43,072 passed, the rest fixed), web 2,943 and ui 1,293 passing, the
  failing integration and security files passing except R-01-T24's order-dependent case, the
  N-01 fixture journeys and TPL-19's visual frames passing locally. DEC-1865 records both rounds.
