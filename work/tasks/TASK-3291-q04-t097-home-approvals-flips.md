---
id: TASK-3291
title: Q-04-T097 home.approvals flips Tue Nov 2 and Tue Nov 9
spec: SPEC-000  # Q-04-T097 row; docs/ops/windows/2027-11-02-home-approvals-flips.md
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T097
branch: s27-q04-t097
created: 2026-11-05
updated: 2026-11-05
---

## Objective
I-01 `home.approvals` flips Tue Nov 2 and Tue Nov 9 per firm.

Acceptance (backlog row): "Both flips are recorded with rollback refs and the flag's retirement is
booked for the Dec bundle."

## Progress log
- 2026-11-05: Rehearsed on PF-X1 and reported as synthetic (DEC-1530, DEC-2081): both instants pass
  `release.window_gate`. Nothing was promoted and no flag was flipped. Rollback refs point at RB-48
  §4 (#1221). Retirement booked for the Dec 14 train in `flag-renewals-2027.md`.
- Found: the flag expires 2027-04-28, before both flips, so the renewal to Dec 30, 2027 is booked too.

## Open (not met here)
Real-firm flips, approvals and verification need a live firm and production (DEC-1391).
