---
id: TASK-917
title: E0 audit-core slice content - 27 audits, Northwind and Granite Peak PBC, portal people, firm settings (F-04-T20)
spec: SPEC-307
acceptance_criteria: [AC-1, AC-3, AC-5, AC-6]
risk_zone: amber
status: done
epic: F-04
plan_key: F-04-T20
branch: f04-t20-audit-core-slice
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Loaded E0 shows 27 audits with exact splits, staff_can_accept_evidence on and BH AJE thresholds
v2 as database rows."

## Plan (amber: written before building)
- **Files.** New `backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/audits.py` with the
  content. It mirrors `apps/web/src/fixtures/seed/{audits,requests,portal}.ts` row for row, with
  the same draws: the 27 §9.7 audits with their teams and creation dates, Northwind's 24 PBC
  requests, Granite Peak's 41, the client people, and the firm setting. `scenario.py` appends its
  events to `audit_core`. `loader.py` gets five handlers.
- **No migration, flag, matrix, registry or product-code edit.**
- **SCENARIO_VERSION** is bumped to `bh-2026.10.2`, and `SCENARIO_HASH` is re-pinned with it.
- **Tests.**
  - `tests/unit/scenarios/test_audit_core_slice.py`: footing before load.
  - `tests/integration/test_scenario_audit_core.py`: E0 loaded into its own Postgres, footing as
    rows, and a second run writes nothing.
- **Rollback.** Revert the commit. A loaded tenant is rebuilt with `make seed-demo` on a fresh
  database.

## What changed
- **Events (all `audit_core`):**
  - `organisations.client_entity_added` ×2: the Northwind and Granite Peak 401(k) plan entities,
    through `organisations.api.client_with_entity`.
  - `engagements.engagement_created` ×27.
  - `identity.portal_user_added` ×4.
  - `requests.pbc_list_created` ×2.
  - `identity.firm_setting_set` ×1.
- **Event times.** Content dated before the firm's setup instant (`SETUP_AT`, Sep 1 8:00 AM CT)
  is replayed at that instant and keeps its own date as `created_at` (Northwind May 28, Granite
  Peak Aug 31). Fairhaven's engagement (Sep 8) and Northwind's PBC ("Requested Sep 1", 10:00 AM CT)
  replay at their own times.
- **Engagements.** Each is written at its stage with deterministic ids (`engagement:A<n>`, the TS
  seed's) by the owner bootstrap: the row, then the trigger-made assurance work item set to its
  phase and due date, the team, and the `engagement.created` audit row. Released maps to Delivered,
  or Archived for A4 and A20. A2 and A7 stay Accepted because their letters are out.
- **PBC lists.**
  - Northwind's is published Sep 1: 11 received, 1 uploaded, 12 requested, so it reads 11 of 24.
  - Granite Peak's 41 are firm-only drafts while G3 is unmet.
  - Categories are `request_categories` rows (family `audit_area`). Dana Kowalski's 9 and Luis
    Ferrante's 41 requests carry them as client assignees.
- **Client people.** Each gets a `users` row on the sink domain (`sink.brightwaterhale.test`), a
  `client` membership, and an engagement-scoped grant: owner for Dana Kowalski and Luis Ferrante,
  `tcwg` for Victoria Lam and Robert Haines.
- **Firm setting.** `staff_can_accept_evidence = true` (DEC-37), set by Grace Holloway.
- **Checked against the TS seed.** A one-off diff of the TS seed's output against this module
  matches every engagement and request: ids, names, created_at, team and entity. The only
  difference is that the Keystone requests have no assignee (see DEC-144).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-144: "BH AJE thresholds v2" is written by K-02-T18 through K-02's import endpoints, not here | No threshold table or import service exists. F-04.10 forbids a constant. No migrations in this task | no |
| DEC-144: Sam Ortiz waits for P-08-T14 (his pending invitation, Sep 2) | Avoids seeding a person P-08-T14 seeds differently | no |
| DEC-144: the shallow audits are written at their stage by the owner bootstrap | Their phases need G1 to G3 and the release and archive gates, which the slice doesn't model | no |
| The fake-model response files are F-04-T25's (responses/README.md updated) | They are keyed by the scenario documents that T25 adds | no |

## Gotchas and discoveries
- The session's `migrated_db` already holds the loader test's E0 with Fairhaven held out. The
  loader skips replayed events, so a full E0 load in the same database would make that test
  order-dependent. The new integration test uses its own database and hands the engine back.
- `request_items_client_assignee` refuses an assignee without an owner or contributor grant on the
  engagement. So client people replay before the PBC lists (handler order).
- **Open for F-04-T31.** The TS seed shows G1 to G3 met for the 25 shallow audits. The loaded
  tenant has no acceptance, independence or letter rows, so its gates read unmet until a slice
  seeds them.

## Progress log
- 2026-10-23: unit 11 passed; integration 2 passed (the new one and the existing loader test);
  scenario and golden suites pass with the re-pinned hash. ruff, pyright, banned_patterns,
  validate_docs, secrets_scan, scope_guards and check-generated were run before the PR.
