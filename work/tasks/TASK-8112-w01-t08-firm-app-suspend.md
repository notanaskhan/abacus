---
id: TASK-8112
title: W-01-T08 rest and W-01-T07 rest — firm-app disable suspends client connections (AC-25, OQ-5); stale-MFA connect answers mfa_required (AC-7)
spec: SPEC-659
acceptance_criteria: [AC-7, AC-25]
risk_zone: red
status: in-review
branch: s46r-w01-t08
created: 2026-11-16
updated: 2026-11-16
---

## Objective
Finish the two W-01 partials S46 left buildable off main (DEC-5083).

## Plan (red)
- AC-7: `integrations/connect_contract._gate` tells a stale second factor apart from every other refusal (`ConnectNeedsMfa`, `facts.reason = mfa_required`), the evidence-exports pattern. WB-10's Enable and Reconnect open the shared step-up (`RevealStepUp`, "Confirm it's you") for it. The AC suite's strict xfail is removed.
- AC-25: migration 0902 widens `connections_status_reason_code_check` and `connection_grant_revocations_reason_check` with `firm_app_disabled`. `connections/firm_app.suspend_for_firm_app(tx, tenant_id, provider)` suspends every live connection of the provider (needs_attention + reason, secret retired, `connection.suspended` audit per row) inside the disable's unit of work; `entity.REAUTH_REASONS` and POR-16's `REAUTH` read it as Needs reauth; the health pass skips it. `connect_service.disconnect_firm` calls it for a firm app and reports the count. `client_connect.start_card` refuses 409 `firm_app_disabled` while a WB-10 firm app is off (connect_v1 on; portal-only feeds never). `StatusReason` gains the value; client regenerated.
- Tests: `tests/integration/test_w01t08_firm_app_suspend.py` (3), the W-01 AC suite, `test_w01t08_connect.py`; web `WB-10.test.tsx` (isStepUp).
- Rollback: revert; 0902 downgrades while no row carries the value.

## Progress log
- 2026-11-16: built and green locally (25 W-01 tests, WB-10 vitest). PRs #2114–#2117 stacked on main 2063b0e55, held for the batch merge.
- Not built (blocked, recorded in S46.md): C-01-T19's intake summary (P-11 sheet classification and C-01-T29's intake mode), C-01-T20's auto-raised issues (C-01-T23/T29), A-09-T13's structure proposal (OneWorld data, A-09-T18), A-09-T19's lock/reopen/TB/export, T-07-T22's appraisal send (SHL-14, T-07-T26).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5083 | Firm-app disable suspends via needs_attention + firm_app_disabled (no new status); POR-16 start waits for a WB-10 firm app | no |
