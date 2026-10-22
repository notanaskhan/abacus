---
id: TASK-391
title: Adopt kernel.clock in red modules, classifying business vs system time (F-04-T11)
spec: SPEC-002
acceptance_criteria: [F-04.4]
risk_zone: red
status: done
epic: F-04
plan_key: F-04-T11
branch: f04-t11-clock-red
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Every red-zone `datetime.now`/`date.today` replaced; MFA, TTL, Object Lock and budgets use
`system_now`" (F-04.4).

## Plan
Classify each call site in identity, agents, connections, evidence, ai_gateway, ledger,
assurance, fieldwork and requests. Security windows, TTLs, caps, retries, infrastructure records
and idempotency nonces take `system_now()`. Times a person sees as "when it happened" take
business time: `now(tenant)` / `today(tenant)` in services, `abacus_now()` in repository
updates (the same function the column defaults use, so a frozen replay or demo clock lines up).
No migration, flag or registry edit. Rollback: revert the commit.

## What changed
- `system_now()`:
  - MFA recency (`identity/authz`);
  - token `auth_time` (`identity/tokens`);
  - OAuth state TTL, revocation and health checks (`connections/connect`);
  - Object Lock retain-until (`evidence/storage`);
  - USD budget windows (`ai_gateway/budgets`);
  - provider-terms dates (`ai_gateway/boundary`, `identity/firm_settings`);
  - route-parity dates (`ai_gateway/routes`);
  - daily action caps (`agents/service`, `connections/service`);
  - rate-limit retry estimates (`agents/activities`);
  - connection expiry, sync and agent run `finished_at`;
  - GL import `updated_at`;
  - fetched-at on raw payloads;
  - the replay window and the 09:00 tick wait (`agents/engagement_agent`);
  - the uuid5 nonces in `draft_start`, `assess_start` and `fieldwork`.
- Business time:
  - the upload view's time (`evidence/uploads`) and the archive lock date (`assurance/completion`): `now(ctx.tenant)`;
  - overdue counts (`requests/routes`): `today(ctx.tenant)`;
  - follow-up chasing and drafting (`agents/follow_ups`): `today_in(zone, await now(tenant))`. `today_in` no longer defaults to wall time;
  - grouping-set `published_at` (`ledger`), agent `paused_at` and follow-up `decided_at` (`agents/repository`): `abacus_now()`.
- Left for F-04-T16: `engagements/setup.py`, `communications/transport.py` and `abacus_tools`.
- `kernel/config.py` keeps a direct `date.today()`, because `kernel.clock` imports config. CLOCK-001 (F-04-T17) has to exempt it or move the check.

## Progress log
- 2026-10-22: built per the S3 batch rules (static checks only; one CI at the end). ruff and pyright are clean on the touched files. The two backfill tests now pass an explicit time to `today_in`.
