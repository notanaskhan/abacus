---
id: TASK-353
title: "F-04-T05 · Interim TS seed: E0 audit-core slice plus portal minimum"
spec: SPEC-307
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6]
risk_zone: green
status: in-review
epic: F-04
plan_key: F-04-T05
branch: worktree-agent-a1c0b98b137d9237c
worktree: agent-a1c0b98b137d9237c
created: 2026-10-21
updated: 2026-10-21
---

> **Rules for the agent working this task**
> - Solo edition: one builder, no approvals, no reviewers to wait for (`docs/plan/AMENDMENT-solo.md`).
> - Frontend only: no `packages/ui` component, no backend code, no push, no CI.
> - Synthetic data only. No real firm, person, EIN, SSN or SSN/EIN-shaped digits anywhere, comments included (the secrets scan blocks them). Money is a decimal string.

## Objective

Give fixture mode (F-04-T04) its data: a typed, deterministic TS seed of the Brightwater Hale E0 audit-core slice and the portal minimum, loadable by `VITE_FIXTURES=1` dev and the `/components` gallery, until the Python scenario's exported fixtures replace it (F-04-T31).

## Scope

**In**
- The plan row: "Typed seed reproduces 46 of 46 seats, 184 clients, 27 audits, Northwind PBC 11 of 24 and the Feld 2025 Binder."
- `apps/web/src/fixtures/seed/`: the 46 seats, the 184 clients (16 named, 66 roster, 102 filler), the 27 audits (A1 to A27) as `EngagementOut` with G1 to G3 gates and one assurance `WorkItemOut` each, the three request lists (Northwind 24, Granite Peak 41, Feld 7) as `RequestItemOut`, the portal users and third parties, the Lena Park to Ashford wall, and Northwind's figures as decimal strings.
- `apps/web/src/fixtures/handlers.ts`, `scenario.ts`, `install.ts`: handlers keyed by OpenAPI path, the `e0` scenario, and the loader.
- Wiring: `main.tsx` (VITE_FIXTURES=1), the gallery's `ScreenPage` through `useSeedFixtures`, `vite.config.ts` and `vite-env.d.ts` for the build-time flag.
- Tests: `fixtures/seed.test.ts`, `fixtures/handlers.test.ts`, `gallery/seed-fixtures.test.tsx`.

**Out**
- The Python scenario package, loader and `make fixtures` export (F-04-T10, T13, T31).
- The seed contamination and canonical-name lint (F-04-T09), screen scenarios (each screen epic), sign-in under `make dev-fixtures` (the app shell still wants a session; the gallery needs none).
- Tax, CAS and advisory slices, the 22 closes, the Harborview, Ridgeline and Bluestem engagements (the epics that need them add their slices).
- The fixture handlers for writes: every handler here is a read.

## Context to load
- Spec: `docs/specs/SPEC-307-brightwater-hale-scenario.md` (AC-1 to AC-8).
- Contracts: `docs/contracts/work-items.md` (C1), `docs/contracts/status-registry.md` (C2), `docs/product/status-vocabulary.yaml`.
- Code: `apps/web/src/app-core/fixture-mode.ts`, `apps/web/src/gallery/fixture-mode.ts`, `apps/web/src/app-core/clock.ts`, `backend/src/abacus/modules/engagements/gate_policy.py`.
- Sources: blueprint 01 §9 (seed universe), handoff ADM-02 (the 46 seats), CLI-01 (the 16 featured clients), ENG-01, AUD-03 (Northwind's 24 requests), BND-02 (the Feld binder), ENG-12 (Granite Peak's 41).

## Plan
- [x] Plan written (green: no approval needed)

Steps:
1. [x] Seed modules: `prng.ts` (seeded, label-derived ids), `people.ts`, `clients.ts`, `audits.ts`, `requests.ts`, `portal.ts`, `index.ts` (`buildSeed`, `getSeed`, `meFor`).
2. [x] Handlers and scenario over fixture mode's own API (`json`, `defineScenarios`, `installFixtureMode`); nothing in `app-core/fixture-mode.ts` is rewritten.
3. [x] Loader and wiring; production folds the flag to a constant, so `dist/` holds no seed.
4. [x] Tests: counts, determinism, run-time validation against `packages/api-client/openapi.json`, registry words, reserved ranges, fixture reads through the generated SDK.

Files to create or change:
- Create `apps/web/src/fixtures/**`, `apps/web/src/gallery/seed-fixtures.test.tsx`.
- Change `apps/web/src/main.tsx`, `apps/web/src/gallery/fixture-mode.ts`, `apps/web/src/gallery/pages.tsx`, `apps/web/vite.config.ts`, `apps/web/src/vite-env.d.ts`.

Rollback: revert the commits. No migration, no dependency, no change to production behaviour (the flag is off outside `make dev-fixtures`).

Tests to write (mapped to ACs):
- AC-1 → seat, client and audit footings; the 14 / 66 / 102 split; Northwind 11 of 24 (13 open); Granite Peak 41; Feld 5 of 7.
- AC-2 → the E0 slice only: 28 engagements (27 audits and the Feld return).
- AC-3 → `buildSeed({ holdouts: ["fairhaven_ebp"] })` is 183 clients and 26 audits; `copperleaf` is 183 clients.
- AC-4 → no SSN-, EIN- or nine-digit-shaped value in the serialised seed; no real mailbox.
- AC-5 → every mailbox is `@brightwaterhale.com` or `@sink.brightwaterhale.test`.
- AC-6 → the footings above are the golden list for this slice.

## Definition of done
- [x] Footings and determinism tests pass; every object validates against its schema at run time and against its type at compile time
- [x] Type check passes
- [x] Lint and format pass
- [x] Full apps/web suite passes (86 files, 749 tests before the final edit; rerun below); no tests skipped, weakened or deleted
- [x] Production `dist/` holds no seed (`gallery/dist.test.ts` is green)
- [x] No new dependencies
- [x] Security scan passes: no secrets, no identifier-shaped digits

Commands:
```
pnpm -C apps/web exec tsc --noEmit
pnpm -C apps/web exec eslint .
pnpm -C apps/web exec vitest run
make check-fast
```

## New dependencies
None.

## Progress log
Append-only. Newest at the bottom.

- `2026-10-21` — Built the seed, handlers, loader and wiring on top of TASK-318's fixture mode. apps/web: tsc, eslint, prettier clean; vitest green.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Ids are derived from labels (`stableId`), not drawn from a stream | Adding or holding out one record must not reshuffle the others (SPEC-307 AC-3 holdouts) | no |
| The two letters still out in this slice (Granite Peak A2, Fairhaven A7) are `accepted` with G3 unmet and blocker `engagement_letter` | ENG-01: four engagements are held at Accepted until their letters are signed; the other two (Bluestem, Ridgeline advisory) are outside the audit-core slice | no |
| Released audits are `delivered`; the two with the archive lock (A4, A20) are `archived` and their assurance item is `archived` | ENG-01 shows Archived 2; A16 reads "archive in 13 days" | no |
| An assurance item's `phase` holds the `audit_engagement` registry codes (planning, fieldwork, in_review, ready_to_release, released) | C1 types `phase` as a string; the registry owns the words | no |
| Granite Peak's 41 requests are `draft` and not client-visible | ENG-01: portal requests stay held until the letter is signed (G3); `draft` is firm-only (C2). The 41 titles are the first n of each category of the FS PBC catalogue (domain-audit.md A.1) because the handoff gives only the count | no |
| The Feld Ridgeline K-1 row is `received` | BND-02 counts it among the 5 of 7 satisfied; the "Draft K-1 · pre-release" word belongs to the `k1_package` object, which is outside this slice | no |
| Firm roles: Grace Holloway and Felix Andersen `firm_admin`, Margaret Okonkwo `practice_leader`, Thomas Whitcombe `quality_partner`; everyone else none | The handoff names job titles, not identity firm roles; this is the closest reading and only `/v1/firm/staff` and `/v1/me` show it | no |
| Offices the sources do not give (some roster audit clients, the signature-envelope clients, filler) are drawn from the 98 / 64 / 62 returns split; relationship partner follows the audit partner, else PR for CAS-only, else the office's tax partner (NA Chicago, VH Denver, DR New York) | Neither field is in any C1 or C2 shape; both are deterministic domain extras for CLI-01 | no |
| Portal mailboxes use `sink.brightwaterhale.test` | SPEC-307 AC-5; the `.test` TLD is reserved, so the address can never reach a real inbox | no |
| Client contact roles are `client_admin` (Dana Kowalski, Luis Ferrante, Claire Feld) and `client_contributor` (Sam Ortiz, Jonah Feld); the benefits committee (Victoria Lam, Robert Haines) holds none | `ClientInvitationIn.role` allows those two values; POR-15 reads as TCWG | no |
| `VITE_FIXTURES` is a build-time constant only in `vite build`; the dev server and tests read it live | A constant keeps the seed out of production; live reading lets a test turn fixtures on with `vi.stubEnv` | no |

## Gotchas and discoveries
- `VITE_FIXTURES` was read by `app-core/clock.ts` but defined nowhere; `make dev-fixtures` therefore started the SPA with fixture mode off. It is now the flag `main.tsx` and the gallery act on.
- Under `make dev-fixtures` the app shell still redirects to sign-in, so the seed answers `/v1/*` for the gallery and for screens a later task mounts without the shell. Faking the session belongs with the first firm-app screen task.
- Secrets scan: variable names containing `key`, `token` or `secret` with string values are flagged, so the seed avoids them; ids are generated at run time, never written as literals. The nine-digit check in the tests strips UUIDs first, because random hex can contain nine digits in a row.
- The lint bans the word "Accrual" in strings; one FS catalogue title was reworded.
- Generated types are thin for people and clients (`FirmClientOut` is an id and a name), so office, partner and portal status live in the seed's domain records, not in API bodies.

## Questions for the human
- [ ] None blocking.

## Handoff
- **Current state:** done and in review; one commit for the seed and wiring, one for tests and this file (see git log).
- **Exact next step:** F-04-T09 (contamination lint) can read `seed.clients` and the roster tables; P-07-T11 builds its CLI and ENG scenarios with `seedScenario()` and spreads `e0.handlers`.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** `docs/plan/backlog.csv` row F-04-T05 still says `todo`; the status column is updated with the batch.
