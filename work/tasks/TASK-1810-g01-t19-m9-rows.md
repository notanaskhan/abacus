---
id: TASK-1810
title: Canary walk and M9 checklist rows (G-01-T19)
spec: SPEC-000  # no G-01 checklist SPEC: G-01 section 10 and the G-01-T19 row
acceptance_criteria: [AC-1]  # G-01-T19: the M9 rows are executable
risk_zone: red
status: in-review
epic: G-01
plan_key: G-01-T19
branch: s13r-g01-t19
created: 2026-10-28
updated: 2026-10-28
---

## Objective
The M9 rows "roles mapped (P-10); walls configured; offshore group consent-gated" executable; the canary walk of j01 3 and j14 1-2.

## Plan (red)
- `identity/security_policies.py` `OperatorPosture` gains four counts (members without a level, active walls, offshore members, consented clients); read-only, operator context.
- `abacus_tools/go_live.py`: `identity.roles_mapped` includes the level count; `identity.walls` executable; new `identity.offshore_consent_gated`.
- Tests: `tests/unit/tools/test_g01t19_m9_rows.py`; the Q-04-T009 item count pins move 20 → 21.
- Docs: pilot-onboarding steps 3.3, 3.5, 3.6; DEC-903.
- Rollback: revert; read-only change.
- **Human:** the canary walk needs production and the canary tenant (neither exists).

## Progress log
- 2026-10-28: built; the go-live unit tests run (25 passed); the collector's integration test runs in the end-of-batch pass.
