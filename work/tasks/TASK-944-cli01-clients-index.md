---
id: TASK-944
title: CLI-01 Clients index a–f on T1, with the clients and engagements fixture handlers (P-07-T11, P-07-T12)
spec: SPEC-321
acceptance_criteria: [AC-6, AC-20, AC-21]
risk_zone: green
status: done
epic: P-07
plan_key: P-07-T11; P-07-T12
branch: TASK-944-cli01-clients-index
created: 2026-10-23
updated: 2026-10-23
---

## Objective
P-07-T11 (wave 1 of the fixtures, the part CLI-01 needs) and P-07-T12 in one change. CLI-01 at
`/clients` behind `clients.v2` on T1: five split filter chips (Status │ Active the amber active
chip), search, the firm's client count in the header (DEC-47), ledger rows newest activity first,
"Load more" over the keyset cursor, a row ··· menu, and the six artboards a–f as fixture scenarios
with tests. Acceptance (P-07-T12): "All six scenarios pass Vitest and axe, Tier C parity is
reported, and the c test proves no wall copy or count renders."

`GET /v1/clients` (P-07-T08) is being built in parallel; the screen uses only the generated
client's `listClients` and its types, and runs on fixture mode until the live route lands. No
backend contract changed.

## What changed
- **UI template** `packages/ui`: T1 `IndexList` takes `countText` (the screen's own count line),
  `actions` (secondary header buttons before "+ New …"), `footer` (under the rows, for "Load
  more") and `searchPlaceholder`; the head and body tables share one `<colgroup>`, which fixes the
  body's columns collapsing to equal widths (BND-01 had the same defect). ViewState
  `filtered-empty` takes an optional `title`. Tests in `index-list.test.tsx`.
- **Fixtures (T11)** `apps/web/src/fixtures/handlers/clients.ts` (`GET /v1/clients` in the
  `ListPage[ClientRowOut]` shape: walls with 404 semantics, the six filters, counts minus status,
  facets, an opaque keyset cursor), `handlers/engagements.ts` (`GET /v1/engagements/index` over the
  seed's 28 engagements, walls, tiles and segments that sum to `total`), `seed/client-rows.ts`
  (the 16 named rows' descriptors, kinds, open requests and last activity; older activity for the
  other 168), `scenarios/CLI-01.ts` (a–f), `clients.foot.test.ts` (12 footing tests). The E0
  scenario now serves both routes, so `make dev-fixtures` has them.
- **Domain** `apps/web/src/domain/clients/` (`queries.ts`: filters, `useClients` over
  `listClientsInfiniteOptions`; `messages.ts`: kind and activity-event words).
- **Screen (T12)** `apps/web/src/screens/CLI-01/` (`index.tsx`, `copy.ts`, `scenarios.ts`,
  `CLI-01.test.tsx`, 20 tests); `routes/firm/clients.tsx` (`/clients` → CLI-01 when `clients.v2`
  is on, the legacy list otherwise); manifest CLI-01 `fixture`; gallery
  `/components/screens/CLI-01?st=a…f`; `app-core/planned.ts` (planned targets hidden in
  production); `e2e/screens/CLI-01.spec.ts` (6 artboards, axe 0 serious or critical, run locally:
  6 passed).
- **Contract** `docs/screens/CLI-01.md`: manifest status, DV-1 to DV-4, open gaps (type pill,
  activity line, Thornbury's seed name, contact search), figures.

## Scenarios
| Artboard | Persona | Data condition | Test |
|---|---|---|---|
| a | grace-holloway | 184 clients, 16 named first, next cursor | "CLI-01a default" |
| b | grace-holloway | Service line │ Audit: the 3 named first, "Showing 25" (DV-3) | "CLI-01b …" |
| c | lena-park | wall to Ashford: absent, `total` 183, no wall words | "CLI-01c …" |
| d | grace-holloway | q=Schwab: no match | "CLI-01d …" |
| e | grace-holloway | `GET /v1/clients` never answers | "CLI-01e loading …" |
| f | grace-holloway | no clients (handler override) | "CLI-01f empty firm …" |

## Not done here (recorded)
- P-07-T11's other screens' scenarios (CLI-02 a–f, ENG-01 a–e, ENG-02 a–g, ENG-03 a–h) and the
  ENG-01 tile footing (1 + 4 + 0 + 128 + 0 + 140 + 2 = 275) wait for their screen tasks (T19,
  T20, T21, T27): the interim seed holds 28 engagements, not the 275 the tiles need. The
  engagements handler and its sum-to-total test are in place for them.
- Gaps in `docs/screens/CLI-01.md`: the type pill needs the entity's tax form; the activity line
  needs an actor and object summary; the seed and Python golden still name the Thornbury client by
  its estate (backend scenario change).

## Checks
- `apps/web`: `tsc --noEmit` (no new errors; the known `packages/api-client/src/{client,core}`
  ones only), `eslint` on the touched files, `vitest run` (all files pass), Playwright
  `e2e/screens/CLI-01.spec.ts` (6 passed).
- `packages/ui`: `vitest run --environment jsdom` and `eslint` on the touched files.
- `make check-generated`; `uv run python -m abacus_tools.quality.secrets_scan` and `scope_guards`.

## Progress log
- 2026-10-23: built T11's clients and engagements handlers and T12's screen; fixed the T1 body
  column widths with a shared colgroup; all checks above green.
