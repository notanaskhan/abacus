---
id: TASK-1000
title: The portal scenario slice — Brightwater Hale branding, the staging portal host, portal people and grants, Sam Ortiz's invitation (P-08-T14)
spec: SPEC-320
acceptance_criteria: [AC-15]
risk_zone: amber
status: done
epic: P-08
plan_key: P-08-T14
branch: s6-portal-scenario-slice
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"make seed-staging produces the branded portal host and every portal persona, with no branding or user content in migrations or constants." (P-08-T14)

## Plan (amber zone)
- **Scenario:** `abacus_tools/synthetic/scenarios/brightwater_hale/portal.py` registers the opt-in `portal` slice: the branding row (POR-01 verbatim), the `brightwaterhale` host label, Claire Feld (`taxpayer`, client), Tess Moreno (`owner`, client entity), Ben Ashby (`contributor`, client entity), Meera Shah (`taxpayer`, her 1040 work item), and Sam Ortiz's pending invitation at Wed Sep 2, 2026. It needs `binders` (Meera's return); the loader adds it. `build()` keeps its default, so `SCENARIO_HASH` holds.
- **Loader:** branding and host go through `portal.api` (`set_branding`, `add_portal_host`, `activate_portal_host`, newly exported) in a unit of work; the host is `brightwaterhale.<portal_base_domain>` from settings, skipped on a laptop without the setting and refused on `--staging` without it. People, memberships, grants and the invitation are bootstrap writes with their audit rows, like `_portal_user_added`.
- **Makefile:** `seed-staging` passes `--slice portal`.
- **No migration, no new table, no product constant.** Rollback: revert the commit; a loaded tenant keeps its rows (staging is reset by `make seed-staging RESET_CLOCK=…` on a fresh database).
- **Tests:** `tests/unit/scenarios/test_portal_slice.py` (registered, opt-in, hash unchanged, verbatim branding, personas and scopes, invitation date and expiry, handlers); `tests/integration/test_scenario_portal.py` (every persona's user, client membership and grant; Dana kept; branding row and active host resolving through `branding_for_host`; Sam's pending invitation; Claire's `read_home` on her household; a second load writes nothing).
- **Deferred (DEC-213):** Tess's TOTP factor (P-08-T17), the invitation's v2 fields and 9-item delegation (P-08-T18), Meera's `k1_recipient` grant (no K-1 package until T-02), POR-02b's Feb 2, 2026 history (no epoch predates the firm's setup).

## Progress log
- 2026-10-24: built. `portal` slice and loader handlers; `portal.api` exports the branding and host writers; `make seed-staging` passes `--slice portal`. Tests: `tests/unit/scenarios/test_portal_slice.py` (8), `tests/integration/test_scenario_portal.py` (1: branding row, active host through `branding_for_host`, the five personas' users, memberships and grants, Sam's pending invitation, Claire's and Tess's homes, idempotent second load). **Found (open, DEC-213):** Meera Shah's `taxpayer` grant on her 1040 work item lists in `portal_scopes` (full shell) but `read_home` answers 404: a `work_item` grant holds no engagement role (DEC-211), so `portal_home.read` (client_admin / client_contributor, `scope_only`) denies it, contrary to Story 6.5. Identity's role derivation (red) owns the fix; the test asserts her scope, not her home. Deferred: Tess's TOTP (T17), invitation v2 fields and 9 items (T18), Meera's K-1 grant (T-02), POR-02b's Feb 2 history.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-213 | What the portal slice seeds now, where the host comes from, and what waits for T17, T18 and T-02 | No |
