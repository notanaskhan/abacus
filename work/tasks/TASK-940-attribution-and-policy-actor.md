---
id: TASK-940
title: Audit rows name only their transaction's person; only the kernel acts as the policy actor (Q-02 AC-15, AC-16)
spec: SPEC-304
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T16
branch: s4-carryover
created: 2026-10-23
updated: 2026-10-23
---

## Objective
Close the two gaps Q-02-T22's independent tests found (#340) in Q-02-T16's attribution.

## What changed
- **AC-15:**
  - Migration `0108_audit_behalf_is_transaction` adds `audit_events_behalf_is_transaction`: `on_behalf_of_user_id` must equal the transaction's `app.on_behalf_of`. It is NOT VALID, because history can't be back-filled.
  - `kernel.db` sets `app.on_behalf_of` from the context for every tenant transaction, and resets it first.
  - Two older test helpers that insert audit rows directly now set the person the same way.
- **AC-16:** new banned pattern `POLICY-001`. A `TenantContext` with actor kind `"policy"` outside `abacus.kernel` is refused.
- Both strict xfails in `test_q02_attribution_access_acceptance.py` now pass.

## Not changed
- F-03-T35's two lifecycle xfails (`prospect` start; `accepted` to `contracted` on the letter) stay. The C1 `EngagementOut.status` is `active | archived`, and P-07's engagement wizard and acceptance tasks (P-07-T16, T35) own that lifecycle.

## Progress log
- 2026-10-23: the attribution, human-only, unit-of-work, chain, session and grant suites (206) pass, as do the quality tests (4720), the full `schema_check` and `make check-fast`.
