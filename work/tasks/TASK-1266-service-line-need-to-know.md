---
id: TASK-1266
title: Service-line need-to-know (migration 0167 need_to_know_v2) — service_line_policies with Audit locked, the service-line reach in authorise and visible(), access.changed on change (G-01-T12)
spec: SPEC-002
acceptance_criteria: [AC-21, AC-22, AC-23, AC-24]
risk_zone: red
status: in-review
epic: G-01
plan_key: G-01-T12
branch: s9a-identity-access
created: 2026-10-26
updated: 2026-10-26
---

## Objective
G-01 §3.10 (AC10.1 to AC10.4) as SPEC-002 Story 6 (AC-21 to AC-24). "Narrowing Tax applies on affected members' next request and Audit can never be widened."

## The open decision (OQ-1, "the Jan 29 decision")
G-01 §0 and OQ-1 leave "Content visible to · Service line" to a red decision that was never
recorded. AMENDMENT-solo item 7: decide with the plan's proposed option. OQ-1's recommendation is
the proposed option: read-only content for members of the line, never Audit or attest, never
walled or non-consented clients, audited, admins still metadata-only. It widens ADR-024, so it is
recorded as DEC-380 and proposed as ADR-183 (amending ADR-024, status proposed), and the reach is
built as narrow and fail-closed as the recommendation allows. No firm is widened by default: a
firm without a policy row reads every line as "Engagement team only".

## Plan (red zone)
- **Migration `0167_need_to_know_v2.py`** (down_revision 0160 in this branch; the main session
  re-points it to the previous merged head): `service_line_policies(tenant_id, service_line,
  enabled, lead_user_id, content_visible_to, cross_line_access, version, updated_by, updated_at)`,
  PK `(tenant_id, service_line)`, CHECKs on the four lines and the two vocabularies, CHECK
  `service_line <> 'audit' OR content_visible_to = 'engagement_team_only'`, lead FK to the firm's
  memberships; `tenant_table` (forced RLS); app may insert the editable columns and update
  `enabled, lead_user_id, content_visible_to, cross_line_access, version, updated_by,
  updated_at`; never delete. Rollback: `alembic downgrade` drops the table.
- **Registry:** `identity/registry.py` TABLES, INSERT_COLUMNS, UPDATE_COLUMNS.
- **Service (`identity/service_lines.py`):** `policies(ctx)` (four lines, defaults for a missing
  row: enabled, team-only, hand-offs only, version 0; `firm.read_settings`, else 404 per ADR-024);
  `set_policy(ctx, line, version, …)` (`service_line_policy.manage`, fresh MFA, live human only;
  422 `audit_locked` for any widening of Audit; 409 `stale_version`; upsert; audit
  `service_line_policy.updated` with codes only; outbox `service_line_policy.changed`; when the
  line's reach changes, `access.changed` for every active member holding the line).
- **authz (protected):** `FirmPolicy.line_reach` (lines a firm opened, read once per request with
  the overrides). A derived pseudo-role, `service_line_reader`, takes the `staff` engagement
  role's cell only for plain reads (no fresh MFA, reason, notify or conditions) and only when:
  a person (not support, not a client user), active staff, not offshore, level not `admin`, no
  firm admin or security admin role, no engagement role on the engagement, the engagement's line
  is open and in the person's `service_lines`, and its client is known not to be an attest client
  (unknown: attest, fail closed). Walls come first, as for every role. At firm level the reader
  counts for reads when the person holds an open line (the rows are then filtered by
  `visible()`). `visible()` gains the same reach in SQL through a new engagements slot,
  `register_engagement_service_line_column`; unregistered, no reach (fail closed). Agents inherit
  it only through the initiator intersection, and the reach grants no write, so no run starts.
- **Routes:** `GET /v1/firm/service-lines` and `PUT /v1/firm/service-lines/{line}` replace the
  501 stubs; `docs/contracts/firm-settings.md` updated; `make generate`.
- **Tests first:** `tests/integration/test_service_lines.py` (AC10.1 to AC10.3 on Postgres:
  defaults, Audit locked in the API and the database, version 409, partner and staff refused,
  the reach granted and narrowed on the next request, lists agree with `authorise`, walls, attest,
  offshore and admins excluded, writes never granted, `access.changed` emitted, cross-tenant).
- **No flag** (authorisation is never flagged; the routes sit behind `firm_settings.v2` like the
  rest of the contract). No seed change: the Brightwater Hale policy values in AC10.1 are firm
  content set through ADM-03h; ADM-03's fixture carries them.
- **Rollback:** revert the commits and downgrade 0167; the routes answer 501 again and every
  line is team-only (the reach reads no row).

## Progress log
- 2026-10-26: plan written (DEC-380 for the decision; ADR-183 proposed).
- 2026-10-26: built. Migration 0167 (down_revision 0160 here; re-point at merge), `identity/service_lines.py`, the `service_line_reader` in `authorise` and `_line_reach` in `visible()` behind the `SERVICE_LINE_REACH` constant, the engagements slot `register_engagement_service_line_column`, routes live, contract doc, SPEC-002 Story 6 (AC-21 to AC-24), ADR-183 (proposed), DEC-380. `test_service_lines.py` 10 pass; the identity unit suite, the generated matrix suite and the walls, G2, visible-scope, firm-policy and offshore suites pass unchanged. `test_schema_check_db`'s pinned update-column contract gained the new table. Note for reviewers: an attest client is read from `clients.is_attest_client`; the test sets it directly (the 0082 trigger did not set it for a superuser insert of an `fs_audit` engagement in `active`, which looks like a later migration narrowing the trigger; not investigated further, outside this task).
