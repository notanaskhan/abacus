---
id: TASK-9011
title: "K-03-T18: Scoping rules engine, rules API, sources and preview"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-k03-t18-scoping-rules
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: K-03-T18
---

## Objective
Row acceptance: Goldens give Harlow & Pike 'Shows 3 steps · 2 sheets · hides 1 · adds 6 requests', Granite Peak 'Shows 1 step · hides 0', rules 2 and 7 answer 422 naming both rules, and no model is called.

## Done
- methodology/scoping.py pure engine with AND/OR, five operators, conflicts
- scoping_rules.py: rules GET/PUT (412, 409 not_draft, 422 rule_conflict / unknown_source), sources, preview
- source providers in engagements and assurance behind a methodology slot
- GET engagement scoping
- goldens unit test and Postgres acceptance test

## Progress log
- `2026-11-26` — Built; goldens 13 passed, Postgres acceptance passed with the gateway replaced by one that fails. Also moved T17's dynamic-table SQL to Core constructs (SQL-001) and clean of the banned-patterns gate.
