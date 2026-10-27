---
id: TASK-1512
title: K-01-T10 Brightwater Hale methodology seed through the services
spec: SPEC-008
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: K-01
branch: s12b-k01t10
created: 2026-10-28
updated: 2026-10-28
---

## Objective
`make seed-demo SLICE=methodology` loads the methodology epoch through the import and approval services with real audit events; golden counts foot 67 steps and 21 mandatory (DEC-652).

## Open
- The 14 EBP pins, the standards sets and `make fixtures` export (DEC-652).

## Progress log
- 2026-10-28: built; lint and pyright clean. The golden unit test and a `seed-demo` run happen in the S12 batch pass.
