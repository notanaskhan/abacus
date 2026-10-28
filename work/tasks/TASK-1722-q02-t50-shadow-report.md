---
id: TASK-1722
title: Q-02-T50 Shadow scoring report and live-stage guard (SPEC-036 AC-5, Q1; QD-10)
spec: SPEC-036
acceptance_criteria: [AC-5]
risk_zone: red
status: in-review
epic: Q-02
plan_key: Q-02-T50
branch: s14-q02-t50
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Backlog row Q-02-T50: `make shadow-report FIRM= AGENT=` scores an agent's shadow outputs against the
firm's people's decisions and computes SPEC-036 Q1 (at least 50 shadow runs and 14 days) and
chapter 10 QD-10 (at least 25 scored decisions, disagreement at most 8%, zero DE-1, DE-4 or DE-5
misses) as a deterministic, versioned export. `agents.api.override_rate` (`override_rate.v1`) is
the only override-rate implementation (Q-04-T008's W7 reuses it). `platform.agent_stage.set`
refuses `live` unless the report it names by SHA-256 passes both.

Acceptance (row): on the rehearsal tenant the report reproduces a hand-computed agreement,
override rate and disagreement exactly, marks each criterion pass or fail, and the stage route
refuses live for a report failing either SPEC-036 Q1 or QD-10.

## Plan (red: the stage guard decides when an agent's output reaches a firm)
- `backend/src/abacus/modules/agents/shadow_score.py` (new): `override_rate()`, the pure `score()`
  and `shadow_score(tenant, agent, as_of)`, which reads shadow `agent_runs` started by `as_of`, the
  screener's `version` screening results on them, and the latest human decision on each made by
  `as_of` (`evidence.api.decisions_on_screenings`; undone decisions excluded).
- `stage_admin.check_live()`: the named report is recomputed as of its own instant and its digest
  compared; no report on failing data is `stage_not_ready`, on passing data
  `shadow_report_required`; a different digest `shadow_report_changed`; a report older than seven
  days or in the future `shadow_report_stale`; a failing criterion `stage_not_ready`
  (`criterion` fact). Error codes registered in `docs/architecture/error-codes.yaml`.
- Route body `report_sha256` and `report_as_of` (contract change, `make generate`); the CLI
  `agent_stage score|set ... <sha> <as_of>`; `make shadow-report`, `make agent-stage REPORT_SHA=
  REPORT_AS_OF=`.
- No migration, no flag. Rollback: revert the PR (the guard goes back to the run-count check).

## Acceptance
| Check | Test |
|---|---|
| Override rate 206 / 3,410 = 0.0604; under 25 decided is no rate | `backend/tests/unit/agents/test_q02t50_shadow_score.py` |
| Q1 and QD-10 edges (49/50 runs, 13/14 days, 24/25 scored, 8.00% passes, 12% fails, each DE miss) | same |
| Deterministic export; digest follows every scored fact | same |
| Hand count reproduced from Postgres; live run, other agent and later decision not counted | `backend/tests/integration/backfill/test_q02t50_shadow_report.py` |
| Route refuses without report, changed digest, stale or future report, failing data; accepts the passing report | same |
| Existing stage behaviour unchanged | `test_q02t07_stage_route.py`, `test_q02t09_optin_independent.py`, `tests/unit/agents/test_agent_stages.py` |

## Progress log
- `2026-10-28` — Built. 11 unit and 3 integration tests pass; the existing stage tests (9 unit,
  8 integration) pass unchanged. Q-02-T44 (its other dependency, the paid Bedrock clearance) is a
  human/money step and does not change this code. DEC-811 records the scoring choices.

## Handoff
- **Current state:** PR open, held for the batch (stacked on Q-04-T011).
- **Next:** Q-04-T008 calls `agents.api.override_rate` for W7; Q-04-T031 runs `make shadow-report`.
