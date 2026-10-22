---
id: TASK-374
title: Database business time and the tenant demo clock (F-04-T06, F-04-T07)
spec: SPEC-024
acceptance_criteria: [AC-5]
risk_zone: red
status: done
epic: F-04
plan_key: F-04-T06
branch: f04-t06-business-clock
created: 2026-10-22
updated: 2026-10-22
---

## Objective
F-04-T06: "One reversible migration passes up/down/up and abacus_now ignores app.now for any
tenant that is not synthetic." F-04-T07: "Demo clock is settable only for synthetic tenants
outside production and each change is audited as firm.demo_clock_changed." (ADR-143; DEC-27)

## Plan (red)
- Migration 0085: `abacus_now()` (invoker; app.now only for a synthetic firm); 111 business
  defaults switched, generated from the database at this revision (list in the migration);
  `audit_events.effective_at` (backfilled, default only; the actor check lifted for the backfill
  and restored NOT VALID); `firm_demo_clocks` with a synthetic-only trigger.
- `kernel.db.session._begin_tenant`: resets and sets `app.now` for a frozen replay or the
  process demo clock, and `app.demo_clocks = on` outside production; `abacus_now()` reads the
  firm's `firm_demo_clocks` row itself, so the clock never opens a second connection (a first
  version did, and the tenancy pooling tests caught it).
- identity: `set_demo_clock` (`demo_clock.set`, firm admin, fresh MFA; refused in production
  and for a real firm; `firm.demo_clock_changed`), `tenant_demo_time` registered as the clock's
  tenant provider (cached 5 s), `clock_view`; `/v1/me` gains `server_now` and `clock_mode`.
- DEC-130. Rollback: revert, downgrade 0085.

## Definition of done
- [x] `tests/integration/test_business_clock.py`: real firm ignores app.now, synthetic follows,
  effective_at grants and defaults, trigger refusal, service set/offset/reset with the audit
  event, real firm and production refused
- [x] `tests/unit/identity/test_demo_clock.py`: frozen, offset (9:24 + 17 min), registration
- [x] Schema up/down/up (integration fixtures); unit, integration, security suites;
  `make check-fast`

## Progress log
- 2026-10-22: built in one session. F-04-T08 (independent tests) follows.
- 2026-10-22: F-04-T08's independent tests (`tests/acceptance/test_f04_business_time.py`,
  F-04.2/.4/.5/.6) added in the same PR as a second commit.
