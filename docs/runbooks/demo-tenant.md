---
title: The staging demo tenant (Brightwater Hale)
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-01-08
---
# The staging demo tenant: load, reset and after-deploy steps

| Field | Value |
|---|---|
| Owner | builder |
| What it is | The synthetic Brightwater Hale firm on staging, at its demo instant (E0: Mon Sep 14, 2026, 9:24 AM CT), for Pilot 0 partner sessions and the staging journeys (F-04.17) |
| Linked from | F-04-T24 (first load), F-04-T34 (this runbook), F-09-T61 (Pilot 0 session scripts); no alarm |
| Rehearse by | Fri Jan 8, 2027: twice by the builder before Pilot 0 (Mon Jan 11, 2027) |
| Last rehearsed | never |
| Kill switches that apply | none; the loader refuses production and any firm that is not synthetic |

This is a procedure, not an incident runbook, so it carries no `RB-<nn>` number. It holds no
secrets, account ids or hosts: those are vault references.

## 0. Rules that never bend
- **Never from a laptop against staging.** Every command here runs as an ECS one-off task on
  staging, after taking the deploy lock (working agreement 3; F-04.16). `make seed-demo` on a laptop
  refuses any database that is not loopback.
- **Never while a deploy runs.** The loader refuses while a `deploy-staging` run is in flight and
  names it; so does `db_guard` while the deploy lock is held. Check first:
  `make deploy-lock ENV=staging` (or `python -m abacus_tools.deploy_lock show --env staging`).
- **Synthetic only.** The loader refuses `environment = production`, and on `--staging` any firm
  whose `firms.synthetic` is false. The demo clock is refused in production (F-04.1). No real
  client data enters the demo tenant (ADR-085).
- **Never `alembic downgrade` on staging** (RB-02). A migration's reversibility is proven on a
  copy (section 4).

## 1. Prerequisites (once)
1. The tenant shell exists: Q-01-T55 provisions the Brightwater Hale tenant on staging through
   `TenantProvisioningWorkflow` (`abacus_tools.tenants provision`, an allowlisted ops command).
2. The portal base domain and the synthetic mail sink are set for staging (the loader refuses the
   `portal` slice without the domain; synthetic mail goes only to the sink, F-04.22).
3. **Gap, partly closed (ED-088):** `abacus_tools.trust_layer_backfill <tenant-id>` is now an
   allowlisted ops command (platform-ops contract section 3.5), so the S9 backfill (section 5)
   runs through `ops-task.yml`. The scenario loader (`make seed-staging`) is still not allowlisted:
   sections 2 and 3 below cannot run as written until it is; do not work around it from a laptop.

## 2. First load (F-04-T24)
1. Take the deploy lock for staging with purpose `demo-tenant-load`.
2. Run the ops task with `make seed-staging RESET_CLOCK=E0`, which runs
   `python -m abacus_tools.synthetic.scenarios.brightwater_hale.loader --staging --snapshot E0 --slice portal`.
   It replays the timeline through each module's `api.py` under each event's person, waits for the
   tenant's outbox to drain and its workflows to go idle after each batch (120 s), then sets the
   tenant clock to `offset` anchored at the snapshot instant (audited `firm.demo_clock_changed`).
3. Release the lock. Expect a second run to be a no-op: identifiers are deterministic, so no new
   rows and no new audit events.

## 3. Reset before a partner session
1. At least 30 minutes before the session, check no deploy is in flight (section 0).
2. Take the lock; run `make seed-staging RESET_CLOCK=E0` (or the session's named snapshot from
   `epochs.py`, e.g. `RESET_CLOCK=2026-09-24` for Granite Peak fieldwork, F-04.18); release it.
3. Verify (section 6). Relative dates ("4 days past due") count forward in real time from the
   anchored instant during the session; that is expected.

Temporal Schedules fire on real time, not on the demo clock; that is accepted under offset mode.
If a pinned clock interferes with timers on staging, F-04 §11 R-2's fallback applies.

## 4. Before a deploy that carries a migration: up, down, up on a copy
Release-specific checks run on a **copy** of staging, never on staging itself.
- **S9 (migration 0172, audit request context; #424; DEC-418, DEC-420):** restore the latest
  staging snapshot to a throwaway instance through the restore drill (`drill.yml`, RB-10), then
  run `alembic upgrade 0172`, `alembic downgrade -1` and `alembic upgrade head` against that copy
  only, and check the audit chain verifies after each step. The downgrade refuses once request
  context or a version 2 checkpoint exists (DEC-420 M1), so run it on the pre-deploy copy. Delete
  the copy afterwards. Production never downgrades 0172 (forward-fix only).

## 5. After a deploy: release-specific one-off steps
Run these after the deploy finishes and the lock is released, each as its own ops task, then
re-run the demo reset (section 3) if the session is that day.
- **S9 secrets, before the deploy (#422; DEC-396):** set `run_record_fingerprint_pepper`
  (environment variable `ABACUS_RUN_RECORD_FINGERPRINT_PEPPER`) in the staging and production
  application secrets, beside the TIN and email-suppression peppers (RB-09 lists them; vault
  reference only, 32 random bytes, never in git, never reused across environments). Unset outside
  local and test runs, agent run records are **not persisted** (fail closed), so set it before the
  S9 image starts. Rotating it changes every new fingerprint: follow RB-09.
- **S9 masked renditions (#419; DEC-369):** for **every tenant** on the environment (the demo
  tenant included), run `python -m abacus_tools.trust_layer_backfill <tenant-id>`. It starts or
  joins `trust_layer_backfill:<tenant>` (v2, `patched("masks")`) on the background queue: each
  source with an extraction and no masked rendition gets its word layer, PII scan and masked
  rendition. Until it finishes, older uploads answer 409 `preview_outdated` on page routes and the
  viewer manifest reads `processing`; that is the designed state, not an outage. It never re-runs
  agents on old uploads and never changes evidence. Watch the workflow in Temporal until it
  completes; a PDF whose word layer can't be read stays without a served page (fail closed).

## 6. Verify
- `GET /v1/me` as Hannah Leclerc answers `clock_mode: offset` and a `server_now` of the snapshot
  instant plus the minutes since the reset.
- The staging journeys pass: `make journeys JOURNEY_ARGS="--project=staging"` from the job that
  sets `ABACUS_STAGING_URL` (J02-audit-core, J12-core and the J04 PBC slice at Sep 24).
- After an S9 backfill: an uploaded W-2 opens in the viewer for an onshore member with its SSN
  masked (`•••-••-` and the last four) and a Reveal chip; an offshore member gets the text view
  only, and every page image answers 403 to them.

## Rehearsal log
| Date | Who | What | Result |
|---|---|---|---|
