---
id: TASK-397
title: Shell scenario data - SHL-03 and SHL-04 seed rows, scenarios and the loader's shell slice (P-01-T07)
spec: SPEC-307
acceptance_criteria: [AC-2, AC-6, AC-8]
risk_zone: green
status: done
epic: P-01
plan_key: P-01-T07
branch: p01-t07-shell-scenario-data
created: 2026-10-22
updated: 2026-10-22
---

## Objective
SPEC-307 AC-2 (a slice), AC-6 (footings and L10) and AC-8 (per-artboard scenarios), for the P-01
epic ACs 2.1.1–2.1.4, 3.1.1–3.1.3, 3.1.7–3.1.9 and 4.1.1.

"The fixture footings hold (PBC 11 → 12 of 24, $16,812,400.00) and the contamination lint is
green." That means TS seed rows and fixture scenarios for every SHL-03 and SHL-04 artboard (rows
a–i, the R2 rows, the Raj variant), plus a loader slice for the live seed (the sandbox
membership, job titles, offices, default office and preferences).

## What changed
**TS seed and scenarios (apps/web/src/fixtures)**
- `contracts/shell.ts`:
  - draft wire types for `/v1/me` v3 and the capability `nav` keys (P-01-T04), built on `MeOut`, `MembershipOut` and `CapabilitiesOut` and shaped by the epic §4.3 table. Delete them when T04's stub is generated;
  - names for parts of the generated C16 types.
- Notifications are typed with the generated C16 types from P-01-T01 (TASK-398, which merged during this task): `NotificationItemOut`, `NotificationFeedOut` and `NotificationPreference(s)Out/In`.
  - The scenarios serve the stub's routes: `GET /v1/notifications/feed`, and `GET`/`PUT /v1/me/notification-preferences` with `{items}`.
  - Row d's facts and subject follow the contract's §8 example.
- `seed/people.ts`:
  - `JOB_TITLES`, the four SHL-03 personas, verbatim from their cards;
  - `DEFAULT_OFFICE_FILTERS`, Hannah → Chicago.
- `seed/shell.ts` (SHL-03 a–f):
  - the firm row "US · Central Time · 46 seats";
  - the training sandbox membership (Grace only), with label-derived ids matching the Python scenario;
  - person card lines and office refs (ids = the loader's `office_id_of`);
  - the default office;
  - capability nav per persona;
  - `meV3For` and `capabilitiesFor`.
- `seed/notifications.ts` (SHL-04):
  - rows a–i at Mon Sep 14, 9:41 AM CT;
  - R2 rows t1–t4 at Thu Oct 1, 11:00 AM. Trigger-row times (3:12 PM, 11:46 AM) come from the built canvas;
  - the Raj Malhotra proposal row;
  - the SHL-04c receipt, the empty-state copy and the four settings kinds;
  - `toWire` and `pageOf` (tabs and counts).
- `scenarios/SHL-03.ts`: scenarios a–f. They answer `GET /v1/me` (v3), `GET /v1/me/capabilities` (nav) and `PUT /v1/me/preferences`. A PUT for an office the tenant does not have gets 404.
- `scenarios/SHL-04.ts`: scenarios a, b, bp (b′), b_raj, c, d, e, f, g and settings:
  - c also serves Northwind's request list with the certified trust report received;
  - f is `never()`;
  - settings serves the GET and PUT preferences.
- Tests:
  - `notifications.foot.test.ts`:
    - PBC 11 → 12 of 24;
    - `prose(netAssetsUnadjusted)` = $16,812,400.00 in row c;
    - every time label equals `time(createdAt)` in the firm zone;
    - the day groups;
    - 28 days from Sep 11 = Oct 9;
    - tab counts;
    - INV-1 inline actions;
    - the settings kinds.
  - `shell.foot.test.ts`: 46 seats, cards against seats, job titles, offices, the default office, the sandbox and the nav per persona.
  - `scenarios/SHL-03.test.ts` and `scenarios/SHL-04.test.ts`: every artboard has a scenario, with its persona, clock and answers.
  - SHL-04 is read through the generated SDK (`notificationFeed`, `notificationPreferences`, `setNotificationPreferences`, `listRequestItems`). Each answer is checked against the OpenAPI schema (`validateResponse`).

**Python scenario (backend/src/abacus_tools/synthetic/scenarios/brightwater_hale)**
- `people.py`: `JOB_TITLES` and `DEFAULT_OFFICE_FILTERS`, mirroring people.ts. A test checks the TS block.
- `shell.py`: `@register_slice("shell")`, 14 events at `SETUP_AT` (Sep 1, 8:00 AM CT):
  - `identity.sandbox_firm_created`: "Brightwater Hale LLP — Training sandbox", `sandbox_of` the firm;
  - `organisations.sandbox_office_created` ×3: the parent's offices, so a staff membership can carry one. Office ids are global keys, so the copies get their own;
  - `identity.sandbox_membership_added`: Grace, Chicago;
  - `identity.job_title_set` ×4: GH, HL, DR, FA;
  - `identity.default_office_set`: Hannah → Chicago, with Hannah as the actor;
  - `notifications.preference_set` ×4: Hannah's four R2 kinds, with Hannah as the actor.
  - Registered from the package `__init__`.
- `loader.py`:
  - handlers for the six new kinds, using the existing bootstrap pattern: an owner transaction plus the audit row. Neither `identity.api` nor `notifications` has a preferences or job-title service yet;
  - `tenant_of(event)`: sandbox events, and their audit rows and skip check, use the sandbox tenant;
  - `load(..., slices=)` and `--slice shell` (added to `audit_core`);
  - `preflight` refuses the whole load with `SchemaPending` until P-01-T04 (`firms.sandbox_of_firm_id`, `memberships.job_title`, `memberships.default_office_filter_id`) and P-01-T03 (`notification_preferences`) have migrated.
- `tests/unit/scenarios/test_shell_slice.py`:
  - the slice is registered and opt-in, and the default hash is unchanged;
  - it is deterministic;
  - its events are dated before E0 and ordered after the seats, with the sandbox first;
  - every kind has a handler;
  - sandbox tenancy;
  - the artboard values;
  - the actors;
  - TS parity;
  - preflight.

**SCENARIO_HASH / SCENARIO_VERSION: unchanged.** `build()` still defaults to `("audit_core",)`, and the golden test passes.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Scenarios live in `fixtures/scenarios/SHL-0n.ts`, not `src/screens/SHL-0n/scenarios.ts` | ESLint forbids `../../` imports from screens into fixtures ("Do not reach across feature roots"). This keeps them inside the L10 scan, and the `seed/` directory stays flat for the determinism test. T08 and T10 wire them into the screens | no |
| Draft types in `fixtures/contracts/shell.ts` for `/v1/me` v3 only | The P-01-T04 stub has not landed (fixture-scenario skill, step 2). The C16 stub (P-01-T01) landed mid-task, so notifications use its generated types | no |
| Facts carry verbatim `title` and `context` beside the contract's facts | No kind templates exist until P-01-T06/T10. Row d also carries the §8 facts, and its `request_item_id` ties it to PBC | no |
| Job titles only for the four SHL-03 personas, verbatim from the cards | SHL-03c shows Daniel as "Tax Partner", but the ADM-02 line is "Tax (signer)", so a title derived from ADM-02 would contradict the artboard | no (open gap below) |
| Settings menu: To-do assigned email on | The built canvas (`KINDS`) has Mention and To-do email on. The revision only says "Mention email stays on", and AC 4.1.1's default (mention only) is marked inferred. This seeds Hannah's state, not the default | no |
| Raj row dated Sep 2, 2:14 PM | Not given on SHL-04. The SHL-10e close activity on the same canvas dates "Run 1 proposed 5 entries · Sep 2, 2:14 PM" | no |
| Nav access levels | `write` for the manage actions, `read` for `firm.read_settings`, `audit_event.read` and the fixture-only `developer_api` (epic §4.3 action mapping) | no |
| The sandbox gets copies of the three offices | Grace's sandbox staff membership needs an office in its own tenant. PLT-01 (G-04) owns real provisioning | no |
| Counts: `client_activity` is 0 | The artboard and canvas show no count on Client activity. P-01-T06 defines the count semantics | no |

## Gotchas and discoveries
- `pnpm -C apps/web exec tsc --noEmit` reports 12 errors, all inside generated `packages/api-client/src/{client,core}/*.gen.ts` (`exactOptionalPropertyTypes`). There are none in app code, and this change touches no generated file.
- A subdirectory under `fixtures/seed/` breaks `seed.test.ts` ("reads neither Math.random nor the wall clock" reads every entry as a file), so the footing tests sit beside `seed.test.ts`.

## Open gaps
- Daniel Reyes: the SHL-03c card reads "Tax Partner · New York", but the ADM-02 title line reads "Tax (signer)". The card wins for SHL-03, and ADM-02 keeps its own line.
- SHL-04 rows are listed in the artboard's order, not by `created_at`. P-01-T06 decides the server's order. The fixture keeps the artboard's.

## Progress log
- 2026-10-22: built the seed, the scenarios and the shell slice. Gates:
  - vitest `src/fixtures`: 8 files, 98 tests, all passed (including L10 in `specimen-figures.test.ts`);
  - eslint and prettier clean on the changed files; tsc has no errors outside generated code;
  - pytest `tests/unit/scenarios`: 31 passed, and the golden hash is unchanged;
  - ruff format, ruff check and pyright clean;
  - `banned_patterns` and `scope_guards` pass.
  - The loader's `--slice shell` path has not been run against a database: it refuses until T03/T04 migrate.
- 2026-10-22: rebased onto the C16 stub (TASK-398) and retyped the notifications against its generated types and routes.
  - The preference audit action follows the contract (`notification_preference.changed`).
  - Gates rerun: vitest 98/98, pytest 31/31, eslint, prettier, ruff, pyright and `banned_patterns` all clean.
