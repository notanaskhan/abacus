---
id: TASK-1516
title: P-03-T26 RB-38 PII reveal review, flag expiries
spec: SPEC-020
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-03
branch: s12b-p03t26
created: 2026-10-28
updated: 2026-10-28
---

## Objective
RB-38 and the alarms' thresholds (DEC-656); the flags keep DEC-137's expiry (F-03-T37's Feb 1 floor).

## Open
- The alarms' Terraform and the staging drill (next infra batch; DEC-656).

## Progress log
- 2026-10-28: runbook and flag expiries; `make regenerate` for the flag registry.
