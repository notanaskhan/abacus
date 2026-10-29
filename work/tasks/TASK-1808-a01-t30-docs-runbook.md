---
id: TASK-1808
title: A-01 docs, binder-export and pilot-rollback runbook, flag plan (A-01-T30)
spec: SPEC-344
acceptance_criteria: [AC-10]
risk_zone: red
status: in-review
epic: A-01
plan_key: A-01-T30
branch: s13r-a01-t30
created: 2026-10-28
updated: 2026-10-28
---

## Objective
A fresh session can run a pilot rollback from the runbook, and both A-01 flags carry retirement dates.

## Plan
- `docs/runbooks/RB-33-binder-export-and-pilot-rollback.md` (+ README index row; next free note moves to RB-39).
- `audits.cockpit`, `audits.binder_export`: "Retires by the Thu May 27, 2027 train" in the registry descriptions (no schema field for it; `_flags.py` unchanged).
- `modules/assurance/README.md` written; `modules/evidence/README.md` export section; `engagement-export-v1.md` frozen v1; SPEC-344 `done`.
- Export alarms: specified in RB-33 §5 (no alarm resources exist in `infra/` for any module yet: Q-01's Terraform). 2 GiB load check: procedure in RB-33 §6, to run on staging (human step: staging does not exist yet).

## Progress log
- 2026-10-28: docs written. Open: wire the two alarms (Q-01), run the 2 GiB check and a rollback rehearsal on staging by May 25, 2027.
