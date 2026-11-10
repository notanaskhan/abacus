---
id: TASK-6504
title: "P-05-T03: collaboration contract stub — classified models, 501 routes, fixtures, docs/contracts/collaboration.md"
spec: SPEC-650
acceptance_criteria: [AC-39]
risk_zone: amber
status: in-review
branch: s33-p05-t03
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-05-T03
---

## Objective
Every comment-thread and to-do route answers 501 under its one matrix action, the client
regenerates, and fixture mode serves every SHL-17 and SHL-18 artboard.

## Plan (amber)
1. `collaboration/contract.py`: classified models and 27 routes (`threads_router`, `todos_router`),
   each: client principal 404, `collaboration.v2` off 404, then 501. Mounted from `api.py`.
2. `make generate`; check no existing schema or operation id changed (renamed `ThreadRedactionOut`,
   `PersonCandidateOut`, `Todo*`/`Thread*` inputs and three route functions that collided with
   requests' SPEC-032 names).
3. `apps/web/src/fixtures/seed/collaboration.ts`, `handlers/collaboration.ts`, a foot test.
4. `docs/contracts/collaboration.md`.
Rollback: revert; no migration.

## Progress log
- `2026-11-09` — Built. Foot test written, not run (end pass). Lesson: generic model names
  (`RedactionOut`, `CandidateOut`, `AssignIn`) and route names (`mention_candidates`) collide with
  other modules' OpenAPI names; check schema and operation-id sets after every `make generate`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3104 | The stub's gate order and the fixture slice's sources | no |
