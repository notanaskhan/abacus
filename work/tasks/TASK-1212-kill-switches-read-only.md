---
id: TASK-1212
title: Kill switches part 2 — read-only mode per platform and per firm (Q-01-T37; P-66)
spec: SPEC-050
acceptance_criteria: [AC-21, AC-27]
risk_zone: red
status: done
epic: Q-01
plan_key: Q-01-T37
branch: s8b-core
created: 2026-10-25
updated: 2026-10-25
---

## Objective
In read-only mode every mutating route answers 503 `read_only` while reads and sign-in keep working (Q-01 F8). The portal sign-in disable (`portal_sign_in`) was already built by P-08-T21.

## Plan
- `identity/routing.py`: the platform row is checked in `AbacusRoute.guarded` before the handler for any non-read route; the firm row by the `firm_writable` dependency, added by `AbacusRouter.add_api_route` to non-read routes authenticated through `current_context` or `current_member`, after authentication has resolved the firm.
- Exempt: pre-session (sign-in) and staff routes, `POST /v1/auth/sign-out`, `POST /v1/portal/auth/sign-out`, `POST /v1/telemetry/errors` (`stays_writable`). Identity routes (sign-up, invitation accept) are refused.
- `read_only` is a 503 detail like `sign_in_paused`; the error-code catalogue holds 409/422 codes only (DEC-338).
- Tests in `tests/integration/backfill/test_q01t36_t37_kill_switches.py`.
- Rollback: revert.

## Progress log
- 2026-10-25: built. Found ED-046 (`PUT /v1/me/preferences` answered 500 on every call: its audit `Ref` held text) and fixed it here, since the read-only test drives that route. Integration 4 passed; `tests/unit/api/test_app_gates.py` passes.
- 2026-10-25: security review fix round (no high findings). Firm read-only now refuses invitation acceptance (`ensure_writable` in the three accept services; `ReadOnlyMode` → 503 `read_only`); support-session approve/revoke/acknowledge, person and staff-invitation revoke and knowledge search stay writable; known limits recorded in DEC-338. Integration file: 5 passed.
