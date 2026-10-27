---
id: TASK-1510
title: I-01-T09 ADR-078 suite for the amber home work
spec: SPEC-308
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: I-01
branch: s12b-i01t09
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Independent AC tests for I-01-T10 (and T12, T13 when they land): admin metadata only, office never a boundary, walls, client and agent refused, the Approvals number (DEC-650).

## Open
- The client activity case is a strict xfail citing this task until I-01-T12 lands; remove it then.

## Progress log
- 2026-10-27: written; lint and pyright clean. Runs in the S12 batch pass, stacked on #511.
