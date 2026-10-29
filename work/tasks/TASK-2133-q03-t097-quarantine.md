---
id: TASK-2133
title: Q-03-T097 Journey and parity reliability 2027 Q2 (quarantine)
spec: Q-03 epic; quality strategy §10.4
acceptance_criteria: [backlog row]
risk_zone: green
status: in-review
epic: Q-03
plan_key: Q-03-T097
branch: s16-q03-t097
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Production-canary journey runs, the flaky-test quarantine kept at 5 or fewer with none older than
10 working days, parity baselines on HANDOFF_VERSION bumps and lock-list hygiene.

Acceptance (backlog row): "The quarantine holds 5 or fewer tests, none overdue, and locked screens
report within tier."

## Progress log
- 2026-10-29: the quarantine (F-01) had no marker, so the quality report's row read "no data".
  Built `abacus_tools.quality.quarantine`: the `quarantine(issue, owner, since)` pytest marker
  (registered) and a `// quarantine: issue= owner= since=` Playwright annotation; at most 5, each
  due within 10 working days; in `make check-fast`; the report row now reads it. The tree holds 0.
  Tests: `tests/unit/quality/test_q03t097_quarantine.py`.
- Locked screens within tier: the visual parity suite runs at the S16 end review. Production
  canary journeys need the production environment: human (Ayush).
