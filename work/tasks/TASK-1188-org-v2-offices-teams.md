---
id: TASK-1188
title: Offices, teams and groups live — migration 0150 org_v2, rosters with history, service-line sync, seasonal bulk date, register_office_facts, CRUD routes (G-01-T08)
spec: SPEC-002
acceptance_criteria: [AC-8]
risk_zone: red
status: in-review
epic: G-01
plan_key: G-01-T08
branch: s8a-org-walls-v2
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"ADM-03a data is live, codes and HQ are unique, and teams foot to 46 with service lines in sync." The row's acceptance is G-01 AC7.1 to AC7.4 (no SPEC of its own; the firm-settings family's spec is SPEC-002, TASK-975's precedent: offices and teams never widen or narrow access, AC-8).

## Plan (red zone)
- **Migration `0150_org_v2.py`** (down_revision 0146):
  - `offices` + `code text NOT NULL` (back-filled from the name: upper-case letters, deduplicated per firm; CHECK `^[A-Z]{2,6}$`; `UNIQUE (tenant_id, code)`), `is_hq boolean NOT NULL DEFAULT false` with a partial unique index (one HQ per firm), `address_line1/2`, `city`, `region_code`, `postal_code`, `lead_user_id` (FK memberships), `default_reviewer_pool_team_id` (FK teams), `version int`. Column UPDATE grant for those plus `name`, `time_zone`; DELETE stays revoked.
  - `teams` + `kind text NOT NULL DEFAULT 'custom'` (CHECK the six kinds), `service_line text NULL` (CHECK `(kind = 'service_line') = (service_line IS NOT NULL)`), `lead_user_id`, `version`. UPDATE grant on `name, kind, service_line, office_id, lead_user_id, version`.
  - `team_rosters` becomes insert-only history (G-01 §4.2 "insert-only with removed_at as a new row", the `work_item_assignments` shape): primary key `id`, `seq bigint` identity for order, `removed_at`, `changed_by`; DELETE revoked. The current roster is the latest row per (team, person) with no `removed_at`.
  - Rollback: `alembic downgrade 0146` (refuses when a roster removal row exists, since the PK would no longer hold).
- **Code (organisations):** `models.py` (new columns), `rosters.py` (history reads and writes, service-line sync), new `org_structure.py` (offices and teams service: list with derived seats and registered facts, create/patch with 409 `office_code_taken`, `one_hq`, `stale_version`; teams create/patch/members; seasonal bulk date through identity), `settings_contract.py` routes live, `slots.py` `register_office_facts`, `registry.py` (insert and update columns).
- **Identity:** `api.sync_service_lines` (the membership half of AC7.4, in the caller's unit of work) and `api.set_seasonal_access_ends` (AC7.3: one unit of work, one audit row per member). People's own writes (`update_person`, `set_member_profile`, invitation acceptance) keep lines and service-line teams in agreement through the slot (422 `person_invalid` `service_lines` when asked to disagree).
- **Registries and gates:** `test_app_gates.py` routes (none added: the stub routes go live), audit target types (`office`, `team` in FIRM_LEVEL), `schema_check` (no definer, no global table).
- **Tests:** `tests/integration/test_org_v2.py` (`test_ac7_1_…` to `test_ac7_4_…`, DEC-30 invariance, history, migration back-fill); the contract suite's T08 routes leave the 501 list; `tests/unit/organisations/test_org_structure.py` (code back-fill rule).

## Progress log
- 2026-10-25: plan written; building.
- 2026-10-25: built. Migration 0150 (down_revision 0146): office code (back-filled; a trigger gives an insert without one the same rule), HQ, address, lead, reviewer pool and version; team kind, service line, lead and version; `team_rosters` insert-only history. `organisations/org_structure.py` serves the eight offices/teams/seasonal routes (live behind `firm_settings.v2`); identity keeps service lines in agreement with service-line teams (`reconcile_service_lines`, the member-teams slot's `lines`). Scenario loader writes CHI/DEN/NYC, Chicago HQ, and team kinds. `tests/integration/test_org_v2.py`: 16 pass (AC7.1 to AC7.4, DEC-30 property, roster history, code rule, line property). Contract suite: T08 routes leave the 501 list; organisations' flag-off gate tested on its own. Schema registries and `test_schema_check_db` pins extended. Deferred: the EQR pool, Monitoring reviewers and Seasonal groups as seeded rows (AY's seed slice).
- 2026-10-25: security review fixes: service-line team changes need `firm.manage_users` (security admins refused); a line a team moves is versioned, audited and emits `access.changed`; the default-code function pins its search path and is not PUBLIC. Tests first: `test_review_*` in `test_org_v2.py` (failed, then pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-317 | Office code back-fill, roster history shape, the service-line sync rule | No |
