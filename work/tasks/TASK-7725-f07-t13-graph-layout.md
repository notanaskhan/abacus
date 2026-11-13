---
id: TASK-7725
title: F-07-T13 graph layout engine
plan_key: F-07-T13
spec: SPEC-652
acceptance_criteria: [AC-6]  # deterministic, no overlap, no edge through a node, pills apart; TPL-14a saved positions exact
risk_zone: green
status: in-review
branch: f07-t13-graph-layout
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Deterministic layered layout (rank by relationship kind, barycentric order, stable tie-break),
orthogonal edge router with label-pill placement, saved positions win; pure functions with
property tests.

## Plan
- `packages/ui/src/graph/layout.ts`, `graph/index.ts` (new); `graph/layout.test.ts`.
- `packages/ui/src/specimens/fixtures/tpl-14.ts` (TPL-14a nodes, edges, spec coordinates).
- Rollback: revert; nothing imports it until GraphCanvas (F-07-T14).

## Partial
- S41 leftovers (TASK-7733): `@abacus/ui/graph` is a subpath of `packages/ui/package.json`; the
  portal lint's `graph` pattern refuses it in portal code (two tests in `f07t20-portal-kits`).

## Progress log
- 2026-11-13: built; eslint and tsc clean; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4728 | the layout and routing rules that make the properties hold by construction | no |
