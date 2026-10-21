---
id: TASK-318
title: "F-04-T01 to T04: scenario spec, kernel.clock, the browser clock and fixture mode"
spec: SPEC-307
acceptance_criteria: [AC-7, AC-8]
risk_zone: red
status: done
branch: task-318-clock
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan
- **T01:** SPEC-307, written from F-04 §3.2–3.4 and ADR-143.
- **T02:** `abacus.kernel.clock`.
  - Functions: `now(tenant)`, `today`, `system_now`, `frozen(at)`, and `register_tenant_clock`, the slot identity fills in F-04-T07.
  - The process demo clock is `ABACUS_DEMO_CLOCK` ("demo" or an ISO instant).
  - `check_startup()` runs in the API, the worker and the migration env, and refuses a demo clock in production.
- **T03:** `apps/web/src/app-core/clock.tsx`.
  - Time order: scenario clock, then `?clock=` (dev, test and gallery builds), then the server offset, then device time.
  - `useNow`, `useToday` and `todayIso` give the Central date, with the US daylight-saving rule computed directly (`Intl` stays `format.ts`'s, F-05-T10).
- **T04:** `apps/web/src/app-core/fixture-mode.ts`: `defineScenarios`, `installFixtureMode` (fetch swapped by OpenAPI path, persona, clock, latency), `json`, `never`.

## Blocked
- **T05, the TS seed:** it must reproduce the canonical figures verbatim from the blueprint §9 seed and the handoff screens (AGENTS.md: never invent data). `$ACCRUED_HANDOFF_DIR` and `$ACCRUED_BLUEPRINT_DIR` aren't set on this machine.

## Definition of done
- [x] `tests/unit/kernel/test_clock.py` (6) passes.
- [x] `src/app-core` tests (7) pass.
- [x] The worker and API unit tests pass.
- [x] check-fast passes.
