---
id: TASK-077
title: Make main green — stale integration assertions brought up to the approved specs (epic F-01-T05)
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: red
status: in-review
branch: task-077-main-green
worktree:
created: 2026-10-19
updated: 2026-10-19
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Red task: test edits need the other founder's approval (ADR-078); the `main` ruleset enforces it.

## Objective
A full stage-2 run on `main` is green, with every changed assertion traced to the approved spec and task that changed the behaviour (epic F-01-T05).

## Scope
**In**
- The 21 integration failures that CI reports on every PR since TASK-055 … TASK-076 (the same 21 reproduce locally on `a42034c`/`9d91bae`).

**Out**
- Coverage floor measurement and any ADR-116 exception (needs a full green CI run first; recorded after this merges).
- CI workflow changes (F-01-T06), nightly e2e (F-01-T08, ayushkbhatia).

## Plan
Three root causes; no product code changes, no test skipped, deleted or loosened.

| Cause | Source of the change | Tests |
|---|---|---|
| New response and contract fields never added to key-set assertions | SPEC-029 (TASK-055, TASK-057), SPEC-031 (TASK-060), SPEC-032 (TASK-062), SPEC-034 (TASK-069), SPEC-035 (TASK-073/074), SPEC-036 (TASK-075/076) | `test_engagements.py` ITEM_KEYS; `test_board_reads_api.py` ITEM_KEYS, VERSION_KEYS; `test_schema_check_db.py` update/insert column contracts and IMMUTABLE_TABLES |
| `ledger_snapshot.recorded` now joins the outbox after a snapshot | SPEC-034 (TASK-069): waiting GL imports restart on it | `test_retrieval.py` (outbox list, quiet-repeat count 1 → 2), `test_retrieval_workflow.py`, `test_observability_flow.py` (select the `evidence_version.created` publish span) |
| Non-synthetic firms' runs start in shadow and are hidden from firm reads | SPEC-036 AC-5 (TASK-076) | `test_board_reads_api.py`: module `world` fixture promotes `evidence.screener` to `live` for the test firm |

## Definition of done
- [x] The six failing files pass locally (551 tests).
- [x] `make check-fast` passes.
- [x] CI: every unit, integration, schema and eval job green on the PR (run 39240016703).
- [ ] ayushkbhatia approves the test changes (ADR-078).
- [x] Coverage recorded: **73%** combined (24,854 statements, 6,268 missed) against `fail_under = 95`; the coverage job fails.
- [ ] Coverage exception with a ratchet to 95 by 2026-12-01 recorded in the two-founder governance ADR (DEC-10; F-01-T02, ayushkbhatia).

## Progress log
- 2026-10-19: CI run 39240016703: all test jobs pass; coverage 73% (floor 95). Lowest: `abacus_tools/workflows/record_*`, `access_review`, `route_parity`, `evals/__main__`, `codegen/feature_flags` at 0%.
- 2026-10-19: reproduced CI's 21 failures locally; traced each to its spec/task; fixed assertions; six files green; stage 1 green.

## Gotchas and discoveries
- TASK-076 was merged with its CI run cancelled, and every PR since 2026-10-09 merged before stage 2 finished — this is how the drift accumulated (F-01-T06 makes stage 2 required).
- `test_observability_flow.py` errors (9) when run in the same local session as the other five files, but passes alone; CI shards run it separately. Watch on CI.

## Questions for the human
- Coverage is 22 points under the floor, far more than T05's "≤ 2 founder-days" back-fill, so the epic's dated exception applies. Never lowering `fail_under`.
- ADR numbering: open PR #133 (SPEC-037) uses ADR-116 and ADR-117, which the epic plan reserves for two-founder governance (P-02) and migration policy (P-38). One side must renumber.

## Handoff
Waiting for ayushkbhatia's approval on PR #134 (the ruleset requires it). The coverage floor stays red until the exception ADR lands or back-fill (Q-03) closes the gap; it is not yet a required check (F-01-T06 makes it one).
