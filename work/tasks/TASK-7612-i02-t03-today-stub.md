---
id: TASK-7612
title: I-02-T03 Today contract stub (TodayVM and the routes), status and glossary rows, fixtures
plan_key: I-02-T03
spec: SPEC-654
acceptance_criteria: [AC-1]  # E0 fixtures render every SHL-23 and HOME-05 state; the contract doc and protected rows
risk_zone: amber
status: in-review
branch: i02-t03-today-stub
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The Today contract stub in `practice`: Pydantic `TodayVM`, `CountCell`, `LeadFact`, `Card`,
`GateRow`, `Group`, `DrillVM`, `HistoryRow` with classification tags; 501 stubs for the five
practice routes and the questions route's shape (workbench); `docs/contracts/today.md`; C2 rows
`daily_briefing` and `attention_item`; glossary rows; the regenerated client; E0 fixtures.

## Plan
- `practice/today/contract.py`, `practice/today/routes.py` (new); `practice/api.py` `ROUTERS`.
- `workbench/today_questions_contract.py` (new): `POST /v1/me/today/questions` (`briefing.ask`;
  both flags 404, then 501); `workbench/api.py` `ROUTERS`.
- `status-vocabulary.yaml` (protected): `daily_briefing` (5 codes, panel and footer context
  labels), `attention_item` (3 derived pills); regenerated `_statuses.py`, `status.gen.ts`.
- `glossary.md` (protected): Today (amended), Daily briefing, Attention item.
- `docs/contracts/today.md` (new); register note on C13.
- `make generate`.
- Fixtures `apps/web/src/fixtures/seed/today.ts`, handlers `fixtures/handlers/today.ts` in the E0
  scenario. The screen contracts' Home route reads `/home?brief=1` (I-02 §3.9).
- Rollback: revert; the flag is off.

## Deviations (DEC-4609)
- The questions route lives in `workbench` (the session owner), not `practice`: practice may not
  import workbench, and the turn is a Workbench session turn.
- `TodayBuildIn.brief_date` (not `date`): a field may not shadow the type; the query parameter keeps
  its name `date` by alias.

## Progress log
- `2026-11-12` — Stub, rows, contract and fixtures built (DEC-4609). Tests run at the S40 end pass.
