---
id: TASK-1238
title: Independent tests for runtime config, the deploy smoke, provisioning and SES, browser errors and the register (Q-01-T31, Q-01-T32, Q-01-T52, Q-01-T53)
spec: SPEC-050
acceptance_criteria: [AC-26, AC-27, AC-31]
risk_zone: amber
status: in-progress
epic: Q-01
plan_key: Q-01-T31; Q-01-T32; Q-01-T52; Q-01-T53
branch: s8b-platform-ops
created: 2026-10-25
updated: 2026-10-25
---

## Objective
- T31: "missing or malformed runtime config fails to a visible error state and no authority or client ID is compiled into deployed bundles".
- T32: the deploy smoke `apps/web/e2e/smoke/deploy-smoke.spec.ts` in a staging project, wired into deploy-staging, 5 minutes or less, axe on each page, a red run fails the deploy.
- T52: "idempotency, the region pin, definer-only synthetic flag, abacus_ops holding no table privileges, and suppression after a simulator bounce".
- T53: "browser payloads carry no URL query, user or breadcrumbs and a missing register row fails the check".

## Plan (amber zone)
- T31: `apps/web/src/lint/q01-t31-runtime-config.test.ts` (no identity-provider authority, client ID, discovery path or `VITE_OIDC_*` in the shipped source or build config). The visible-error half waits for Q-01-T23 (not built: a missing file leaves reporting off and the app boots).
- T32: `apps/web/e2e/smoke/{playwright.config.ts,deploy-smoke.spec.ts,sign-in.ts}`; projects `deploy-smoke` and `canary-smoke`; edge headers and blocked `/healthz`, `/readyz`; the release's `runtime-config.json`; signed-in sign-in and engagements list with axe behind `SMOKE_SIGN_IN=on`. The upload, EICAR and simulator-mail steps wait for the smoke user's binder and the sink mailbox reader (F-04-T22). The main Playwright config ignores `e2e/smoke`.
- T52: `backend/tests/integration/test_q01t52_provisioning_ses_independent.py`, run as the roles themselves.
- T53: `apps/web/src/app-core/telemetry.independent.test.ts`; `backend/tests/unit/quality/test_q01t53_register_drift_independent.py`.
- Same-session authorship in a solo lane: ADR-078 independence is nominal for all four.

## Progress log
- 2026-10-25: T31 (2 vitest), T32 (spec lists 4 tests across the two projects; never run: no staging), T53 (3 vitest, 8 pytest) written and green.
