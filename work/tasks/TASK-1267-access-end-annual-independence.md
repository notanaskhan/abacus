---
id: TASK-1267
title: Seasonal access end and annual independence (migration 0168 annual_independence) — the hourly access-end job with the T-7 notice, the statement and confirmation tables and API, has_current_annual_confirmation for P-07 (G-01-T13)
spec: SPEC-024
acceptance_criteria: [AC-9, AC-10, AC-11, AC-12]
risk_zone: red
status: in-review
epic: G-01
plan_key: G-01-T13
branch: s9a-identity-access
created: 2026-10-26
updated: 2026-10-26
---

## Objective
G-01 §3.4 AC4.5 and §3.6 AC6.1 to AC6.3, as SPEC-024 AC-9 to AC-12: "On Nov 2, 2026 the five
seasonal members are deactivated by the job, and P-07 reads Kevin's confirmation."

## Plan (red zone)
- **Migration `0168_annual_independence.py`** (down_revision 0167): `independence_statements`
  (the firm's statement, one row per version; firm content, never seeded), `independence_annual_
  confirmations` (insert-only; `seq` orders answers, the newest per person and year wins; CHECK
  `actor_kind = 'human'`; a decline needs a note; FK to the statement version), `access_end_notices`
  (one per firm and date: the T-7 notice's idempotence). All `tenant_table`, insert-only triggers,
  column-level INSERT grants. Rollback: `alembic downgrade 0167` drops the three tables.
- **Job (DEC-381):** `identity/access_end.py` + `identity/workflows.py` `AccessEndSweepWorkflow`
  on the Schedule `access_end:platform`, hourly, background (Q-01-T26's platform-job pattern,
  DEC-359; the epic's "worker side job" predates the Schedules). New workflow: no patch needed;
  its v1 history is recorded (`access-end-v1-swept.json`) and replayed (ADR-090). Firms are listed
  through the identity role (it already reads `firms.tenant_id`; no new grant, no cross-firm
  definer: the owner is bound by forced RLS); each firm is swept in its own session at its own
  business date (`kernel.clock`, firm time zone). Deactivation reuses `membership_deactivate`
  (reason `access_ended`, `on_behalf_of` = who last set the date, from the audit trail), revokes
  invitations, ends sessions, emits `membership.deactivated` + `access.changed`.
- **Notification:** `membership.access_ending` -> C16 `seasonal_access_ending` to firm admins.
- **Confirmation API:** `GET /v1/firm/independence/annual` live (`independence.annual_read`);
  `POST /v1/me/independence/annual` live (`independence.annual_confirm` through a new
  `authz.authorise_own`: the action is self-only and firm-level, so a staff member without a firm
  role or engagement holds it — plain `authorise` would refuse them, ED-069); new
  `GET /v1/me/independence/annual` (`OWN`: one's status and the statement),
  `GET`/`PUT /v1/firm/independence/statement` (`firm.read_settings` / `firm.manage_settings`).
  `PersonOut.annual_independence` filled. `identity.api.has_current_annual_confirmation`.
- **Contract:** `firm-settings.md`, `make generate`; the contract test's LIVE set; the stub gate
  test becomes a flag gate test (no stub is left).
- **Tests first:** `test_annual_independence.py`, `test_access_end.py`; the platform-schedule
  integration test and the replay test extended; the catalogue pin extended.
- **Not done here:** the human-only audit register (`abacus_human_only_actions()`) is not
  extended with `independence.annual_*` (it needs a migration redefining a function other
  workstreams may redefine in this wave); the table's `actor_kind = 'human'` CHECK holds instead.

## Progress log
- 2026-10-26: plan written and built; tests green (see the commit).
- 2026-10-26: built and green: `test_annual_independence.py` 7, `test_access_end.py` 6, the platform-schedule integration test (with the new job), the platform-job replay test (new `access-end-v1-swept.json`, recorded with `abacus_tools.workflows.record_platform_jobs` against throwaway containers from the compose images), the contract, catalogue, people, firm-settings, schema-check and route-introspection suites. `make generate`; `security_tests` codegen regenerated (route list). A first draft used a SECURITY DEFINER to list members across firms; the owner is bound by forced RLS (the same trap as SPEC-013's purge, #380), so the job lists firm ids through the identity role instead.
