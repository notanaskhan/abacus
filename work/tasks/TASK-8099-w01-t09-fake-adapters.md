---
id: TASK-8099
title: W-01-T09 Fake adapters (firm token, personal OAuth, firm app, file bridge), production boot refusal, conformance suite for health and revoke
spec: SPEC-659
acceptance_criteria: [AC-4, AC-10, AC-11, AC-14, AC-24]
risk_zone: red
status: in-review
branch: w01-t09-fake-adapters
created: 2026-11-15
updated: 2026-11-15
---

## Objective
Fakes that let the synthetic tenant show every WB-10 and WB-11 state without a real provider, never in production (DEC-5073).

## Plan (red)
- `kernel/config.py`: `integrations_fake_adapters` (default off) and a validator that refuses it in production (API and worker load settings at boot). Rollback: remove the setting; nothing persists.
- `integrations/ports.py`: `ConnectPort`, `TokenGrant`, `HealthOutcome`, `ConnectRefused`.
- `integrations/connect_ports.py`: the port allowlist and fail-closed registry.
- `integrations/fakes.py`: the four fakes, scripted health; `adapters.adapter_for` returns a fake read adapter on a synthetic firm only.
- Tests: `tests/unit/integrations/test_w01t09_fakes_conformance.py`, `tests/unit/kernel/test_config.py` (production refusal).

## Progress log
- 2026-11-15: built; conformance and config tests green; stacked on #2098.
