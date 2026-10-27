---
id: TASK-1368
title: Main CI fixes on 30222ac3 (bundle budget, logging leak, four integration failures)
spec: SPEC-000  # no SPEC: a CI fix across F-05-T17, AC-20, SPEC-013, P-04-T13, F-04-T29, P-08-T10, AC-16
acceptance_criteria: [AC-1]  # run 40466452421's stage 1, unit and integration failures pass
risk_zone: red  # portal sign-in (ED-132) and the AI gateway (ED-133)
status: in-review
epic: Q-03
plan_key: none
branch: ci-fixes-2
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Main's first full CI run in a while (`30222ac3`, run 40466452421) is red. Fix each cause without
weakening a test, lowering a threshold or raising a budget. Decisions DEC-464, DEC-465; defects
ED-131, ED-132, ED-133. Deferred by Ayush and left alone: `src/status/status.test.ts` and the
gallery visual-regression timeout.

## Plan (red)
- **Bundle budget** (firm initial 261.9 KB of 250): Q-01-T23 (#460) made `main.tsx` await the
  runtime config at the top level. An entry with a top-level await makes Rollup split every module
  it shares with a lazy route into its own chunk (17 initial chunks became 49), so the same code
  gzipped 12 KB larger. Boot through a promise chain instead, in both entries (DEC-464).
- **AC-20 logging** (`too many values to unpack`): `test_a02t19_registry_independent.py` (#478)
  ran the API lifespan to its end, which shut the process-global tracer provider down; every
  later span end on that xdist worker logged "Processor is already shutdown" into the JSON log
  stream. The test now stubs the lifespan's `shutdown_tracing` and `flush_errors`, as
  `test_api_observability_scrubbing.py` does.
- **Notification email** (ED-131): fixed in `notifications/email.py` (sentence by kind and subject
  type) and `repository.delivery_facts` (subject type).
- **P-04-T13 human-only probe**: 0213 (P-04-T23) added `decisions_decider_is_the_actor`, which also
  refuses every non-person writer. The probe test now asserts that guard holds alone, then drops it
  too before expecting the probe to find the hole.
- **F-04-T29 loaded goldens**: two tests read the E0 the first test loaded into the module's own
  database; under `--dist loadgroup` they ran on another worker against an empty one. The module is
  one `xdist_group`, and each test loads E0 itself when it runs first.
- **Portal sign-in AC7** (ED-132): a real deadlock, fixed with a per-challenge advisory lock in
  `portal_session.verify_code` (DEC-465).
- **Gateway AC-16** (ED-133): not pollution. The serial phase ran it alone in a fresh process; the
  0.1 s timeout also covered the boundary check and the access events, so a cold first database
  round trip timed out before the provider started. The timeout now bounds the provider call only.
- No migration, no generated-file change, no new dependency. Rollback: revert the commit.

## Progress log
- 2026-10-27: built and verified (counts in the commit report). `firm initial` is 249.9 KB of
  250 KB after the fix (249.5 KB on 1aed1484): the margin is thin and the next initial-load growth
  will trip it; `shell/firm/NotificationsDrawer.tsx` (17 KB raw, opened from the bell) is the
  largest candidate to make lazy. The portal build's POR-04 route chunk is 120.4 KB of 120 KB,
  over before this change too (120.3 KB on 1aed1484); CI does not build the portal, so it is
  reported, not fixed here.
