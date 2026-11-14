---
id: TASK-8019
title: "T-07-T05: contract stubs for the fiduciary and estate families"
spec: SPEC-656
acceptance_criteria: [AC-15]
risk_zone: amber
status: in-review
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
- `2026-11-14` — Built. `tax/fiduciary_contract.py` (25 routes), `tax/estate_contract.py` (11 routes), wired in `tax/api.py`; three refusal codes in `error-codes.yaml`; client regenerated (75 schemas added, none removed or qualified); `docs/contracts/fiduciary-workpapers.md`, `estate-workpapers.md`, README rows; footing fixtures `calloway_2025.json`, `thornbury_706.json`. ruff and pyright clean on the new files; tests at the end pass.
- **Partial.** Stubs answer 501, not seed-derived fixtures (the T-04/T-05 pattern); the typed fixtures carry the footing for T06's tests and the FE's fixture handlers.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
