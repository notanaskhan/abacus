---
id: TASK-3296
title: Q-03-T186 Journey and parity reliability 2027 Q4
spec: SPEC-000  # Q-03-T186 row; docs/quality/sweeps/2026-11-05-q03-t186-parity-reliability.md
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: Q-03
plan_key: Q-03-T186
branch: s27-q03-t186
created: 2026-11-05
updated: 2026-11-05
---

## Objective
Production-canary journey runs, flaky-test quarantine at 5 or fewer and none older than 10 working
days, parity baselines on HANDOFF_VERSION bumps and lock-list hygiene.

Acceptance (backlog row): "The quarantine holds 5 or fewer tests, none overdue, and locked screens
report within tier."

## Progress log
- 2026-11-05: Quarantine 0. Full parity on 1.64.1: 215 locked rows measured, 27 over tier and
  47 unmeasured. The manifest's `tools` block moved to 1.64.1. No lock, threshold or mask changed.

## Open (not met here)
- 27 locked rows over tier, 47 locked rows unmeasured, cause not established.
- Production-canary journeys need a deployed environment.
