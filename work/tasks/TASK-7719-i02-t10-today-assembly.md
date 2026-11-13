---
id: TASK-7719
title: I-02-T10 practice.today assembly and live routes
plan_key: I-02-T10
spec: SPEC-654
acceptance_criteria: [AC-1.1, AC-1.2, AC-2.1]
risk_zone: amber
status: in-review
branch: i02-t10-today-assembly
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
The Today read model by code over C13: cells, lead facts, cards, needs-you-first, groups and the
drill-in, live on `GET /v1/me/today` and the drill route.

## Plan (amber)
- `practice/today/assembly.py` (new), `practice/today/routes.py` (two routes answer),
  `review/api.py` (`resolve_gate_facts`), `agents/briefing/today.py` + `agents/api.py`
  (`latest_briefings`).
- Tests: `backend/tests/unit/practice/test_i02t10_today_assembly.py`.
- Rollback: revert; the routes answer 501.

## Partial
- `POST /v1/me/today/builds` (three forced a day) and history stay 501: the stub's split gives
  builds to I-02-T13 and history to I-02-T16.
- Groups `high_risk` (briefing risk lines) and `running` (runs count) are not assembled; the
  per-persona E0 figures (Daniel 3·6·2·0, Margaret 2·0·2·0) are checked at the end-pass load.
- Assign prefills and downstream rows in the drill-in wait for I-02-T11's providers.

## Progress log
- 2026-11-13: built; OpenAPI export clean; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4722 | the assembly rules and the build/history split | no |
