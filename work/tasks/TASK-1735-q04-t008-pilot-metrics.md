---
id: TASK-1735
title: Q-04-T008 PilotMetricsWorkflow
spec: SPEC-349
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T008
branch: s14-q04-t008
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Weekly W4–W7 pilot snapshots on a Temporal Schedule. Acceptance (backlog row): "On the rehearsal
tenant one snapshot per metric per week is written, a rerun is idempotent every value matches a
hand count of the seeded events, and W7 equals make shadow-report's override rate on the same
decision set."

## Plan (amber)
- `platform/pilot_metrics.py`: the source slot, `compute_week`, `last_week`.
- Sources: `engagements/pilot_w4.py`, `requests/pilot_w5.py`, `audit_trail/pilot_w6.py`,
  `agents/pilot_w7.py` (+ `agents.shadow_score.live_override`), `organisations.portal_activation`.
- `PilotMetricsWorkflow`, activity, Schedule (`PlatformSchedule.weekly`), `make pilot-metrics`,
  `abacus_tools.pilots metrics`. DEC-825.
- Rollback: pause the Schedule; revert. Snapshots are insert-only and harmless.

## Acceptance
| Check | Test |
|---|---|
| One snapshot per metric, values match a hand count | `backend/tests/integration/backfill/test_q04t008_pilot_metrics.py::test_ac_one_snapshot_per_metric_matching_a_hand_count` |
| A rerun is idempotent | `…::test_ac_a_rerun_is_idempotent` |
| W7 is the shadow report's function | `…::test_ac_w7_is_the_shadow_reports_override_function` |
| Exited skipped; Monday weeks | two tests |

## Progress log
- `2026-10-28` — Built. ruff, pyright, lint-imports, banned patterns clean. Tests written, not run
  (end-of-batch review). A first cut imported agents and requests into platform: lint-imports
  caught the cycle; the slot replaced it.

## Handoff
- **Current state:** PR open, held for the batch.
- **Next:** N-02-T10.
