---
id: TASK-8019
title: "T-07-T05: contract stubs for the fiduciary and estate families"
spec: SPEC-656
acceptance_criteria: []
risk_zone: amber
status: in-progress
branch: t07-t05-stubs
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: T-07-T05
---

## Objective
contract stubs for the fiduciary and estate families.

## Plan
Files: `tax/fiduciary_contract.py` (TXT-01/02/03 routes), `tax/estate_contract.py` (TXT-04 routes), each route one action, flag-gated 404, 501 until its build row (repo pattern, T-04/T-05); classified models (TRI on figures, Confidential instrument refs, no clause text); `docs/contracts/fiduciary-workpapers.md`, `estate-workpapers.md`; `tax/api.py` ROUTERS; `make generate` and diff `components.schemas` against main (S44 lesson). Typed footing fixtures for T06 under `tests/contracts/fiduciary/fixtures/`.

## Progress log

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
