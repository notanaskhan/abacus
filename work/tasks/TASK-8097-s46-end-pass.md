---
id: TASK-8097
title: S46 end pass — gates, suites and fixes for the S46 stack
spec: SPEC-655
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: s46-end-pass
created: 2026-11-15
updated: 2026-11-15
---

## Objective
Run the S46 end pass (AMENDMENT-solo §7) once over the stacked S46 rows and fix what it finds.

## Progress log
- 2026-11-15: client regenerated; `make check-fast`, full pyright, full unit suite and web vitest green; S46 integration files, tenant isolation and the security suite green under the test lock; schema_check clean. Fixes: kernel slots for the ledger sync scope and connection coverage (BOUND-002); migration 0900 and the ledger sync's column-grant writes (DEC-5071); close intake publishes through `set_binder` and sets visibility and due dates after insert; 0896's NULL target CHECK; recorded replay histories (ledger sync, request publish, JE scoring); web overlay wiring for AUD-33 and SHL-09. PR #2097.
