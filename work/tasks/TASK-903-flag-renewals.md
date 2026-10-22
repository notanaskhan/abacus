---
id: TASK-903
title: Renew or retire the flags expiring before Feb 1, 2027 (F-03-T37, founder override DEC-137)
spec: SPEC-307
acceptance_criteria: [AC-7]
risk_zone: red
status: done
epic: F-03
plan_key: F-03-T37
branch: f03-t37-flag-renewals
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"make check-fast passes with no flag expiring before Feb 1, 2027 and no flag owned by 'founder'."

## What changed
- **Founder override (DEC-137):** a flag entry may carry `override: DEC-nnn`, which allows a renewal of up to 180 days. Without it, the 90-day lifetime still holds. The generator refuses an override that doesn't name a decision.
- **Renewals:** all 16 flags that expired before Feb 1 run from 2026-10-23 to 2027-04-21, after the busy-season freeze. `engagements.work_items_api` was re-dated.
- **Tests:** `tests/unit/tools/test_feature_flag_override.py` covers the 90 and 180-day limits and the decision name, and checks the acceptance (no expiry before Feb 1, no "founder" owner) against the real registry.
- `docs/plan/status/flag-renewals-S4.md` records each flag.

## Progress log
- 2026-10-23: Ayush overrode the 90-day rule so this task runs now rather than on Dec 14–18. The registry is regenerated and the tests pass.
