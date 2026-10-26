---
id: TASK-1303
title: C13 home-half stub - HomeVM models, 501 GET /v1/home behind home.dashboard, the home-count slot (I-01-T02)
spec: I-01 §4.3, §8.2
acceptance_criteria: [I-01-T02]
risk_zone: amber
status: in-review
epic: I-01
plan_key: I-01-T02
branch: s10-i01-home
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Contract first for HOME-01: the `HomeVM` shapes, the route and its flag, the platform slot owners
register tiles through, the matrix action, status words and glossary rows, so I-01-T10 and the
fixtures (T05) build against a frozen home half.

## Plan
- `practice/home_contract.py`: `HomeOut` and its parts, every field classified; `GET /v1/home`
  (`home.read`): client 404, `home.read` at the firm (403), `home.dashboard` off 404, on 501.
  Mounted in `practice.api.ROUTERS`.
- `platform/slots.py`: `register_home_count(key, provider)`, `home_count` (fail closed: no tile
  for an unregistered key or a provider that raises), `HomeCount` and its parts; re-exported
  from `platform.api`.
- Matrix `permission-matrix/practice.yaml` (`home.read`: every firm role; client roles, agent and
  system deny); flag `feature-flags/practice.yaml` (`home.dashboard`, DEC-137 expiry).
- Status words `human_gate` and `due_risk`; glossary rows (Waiting on you, Snooze, Client
  activity, Home count).
- `docs/contracts/home-and-gates.md` (home half, the gate half summarised from P-04 and I-01) and
  the register row; `make regenerate`, `make generate`.
- Provider stub tests `tests/contracts/c13_home/test_home_stub.py`.
- No migration. DEC-404 records the choices.
- Rollback: revert; the flag stays off.

## Progress log
- 2026-10-26: built; matrix, flags, statuses and the API client regenerated. Tests run in the
  end-of-batch targeted pass.
