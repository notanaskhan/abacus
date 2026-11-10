---
id: TASK-3294
title: Q-03-T184 Security and reliability sweep 2027 Q4
spec: SPEC-000  # Q-03-T184 row; docs/quality/sweeps/2026-11-05-q03-t184-security-sweep.md
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T184
branch: s27-q-03-t184
created: 2026-11-05
updated: 2026-11-05
---

## Objective
The compliance invariant catalogue run end to end, generator coverage audit, DAST, Inspector and
GuardDuty triage, and the ADR-093 reliability follow-ups.

Acceptance (backlog row): "Every new table and condition kind has generated tests, no high DAST or GuardDuty finding is open and every burn-rate alert has a closed follow-up or a dated ticket."

## Progress log
- 2026-11-05: generator coverage 0 gaps, and main's `security` CI job passed. AWS read-only calls
  refused: "Your session has expired". `dast.yml` skipped on its recent runs.

## Open (not met here)
- DAST, Inspector and GuardDuty triage: not done (no findings read).
- Burn-rate follow-ups: not done (no alert data read).
