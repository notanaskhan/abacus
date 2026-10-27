---
id: TASK-1421
title: The firm follow-up policy and the policy-driven P-4 tick (R-01-T24; DEC-74)
spec: SPEC-345
acceptance_criteria: [AC-6]
risk_zone: red
status: in-review
epic: R-01
plan_key: R-01-T24
branch: s11-comms
created: 2026-10-27
updated: 2026-10-27
---

## Objective
R-01-T24's acceptance: with a 5-day cadence the next reminder after Mon Sep 14 is Mon Sep 21, a
marked-done binder gets no further draft, and the pre-change P-4 history replays.

## Plan
- **Migration 0221 `follow_up_policies`** (down_revision 0220): one row per firm, PK
  `tenant_id` (FK firms), the DEC-74 fields with R-01 §4.2's checks and defaults, `version`,
  `updated_by` (FK memberships), `updated_at`; forced RLS (`tenant_table`); the app inserts the
  content columns and updates them (no delete). No row: the defaults apply (7 days, at most 4,
  weekdays 09:00, stop when done, notify after the maximum, draft for a person).
- **Code** (`communications/follow_up_policy.py`): `follow_up_policy(tenant)` (the row or the
  defaults), `save_follow_up_policy(ctx, fields, expected_version)` (`portal_settings.manage`,
  fresh MFA by the matrix; `expected_version` 409 `stale_version`; audited
  `follow_up_policy.saved`; for R-01-T26's portal-settings publish), the pure
  `next_send_at(policy, last_sent_at, zone)` (cadence in calendar days from the last send's local
  date, a weekend shifted to Monday when `weekdays_only`, at `send_local_time` in the recipient's
  zone; until contacts carry a zone, the firm's) and `GET /v1/firm/follow-up-policy`
  (`portal_settings.read`; `next_send` for the sample client: the last send is today's
  `send_local_time`).
- **P-4 tick** (`agents/follow_ups.py`, `engagement_agent.py`, the workflow): the
  `EngagementAgent` workflow's tick event carries `{"follow_up_policy": "v1"}` under
  `workflow.patched("follow_up_policy_v1")`; the tick activity then reads the firm's policy and
  each binder's override (P-06's `follow_up_override`, which wins): cadence and maximum from
  them, no draft for an item whose binder the client marked done (`stop_on_binder_done`), and once
  the maximum is reached `follow_up.limit_reached {engagement_id, binder_id, contact_id}` on the
  day the next one would have been due (notification kind `follow_up_limit_reached`, undotted per
  C16, to the engagement's leads). Without the marker (recorded histories, in-flight runs that
  replay) the legacy constants apply, so v1 and v2 histories replay unchanged.
- **send_on_schedule**: with the policy's mode `send_on_schedule` and `follow_ups.scheduled_send`
  on, the tick sends each due reminder through `send_templated(SystemSendContext, "reminder")`
  (published version only, attributed to its publisher, the client-mail checks) and records it
  as a sent follow-up with `follow_up.scheduled_sent` (actor system); otherwise it drafts for a
  person, as today. Agent text never goes out this way (DEC-74).
- **requests**: `OverdueItem` gains `binder_id`, `binder_marked_done`, `binder_override` (read
  in the same query).
- **Registry**: communications `TABLES`, `INSERT_COLUMNS`, `UPDATE_COLUMNS`; `schema_check`
  expectations in `test_schema_check_db.py`; audit owner for `follow_up_policy`;
  `activity_reviewed` gains `follow_up_policy.saved`, `follow_up.scheduled_sent`; notification
  catalogue and kind; worker exact lists where the catalogue is enumerated.
- **Tests first**: `tests/unit/communications/test_follow_up_policy.py` (next_send_at: Sep 14 + 7
  → Sep 21, + 5 → Sat Sep 19 → Mon Sep 21, zones), `tests/unit/agents/test_follow_up_policy_plan.py`
  (override wins, done binder skipped, maximum then limit reached once),
  `tests/integration/test_r01t24_follow_up_policy.py` (GET, defaults, save with stale 409, RLS,
  a marked-done binder gets no draft through the tick), `tests/workflows` (the v1/v2 histories
  replay; the patched marker is the payload's only change).
- **Rollback**: downgrade drops the table; the code reads defaults when there is no row, and the
  tick falls back to the constants without the marker.

## Progress log
- 2026-10-27: planned (S11 lane 5).
