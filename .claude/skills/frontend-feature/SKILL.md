---
name: frontend-feature
description: How to build a frontend screen or component — design system, generated API client, states, accessibility. Use for any web app work.
---

# Frontend feature pattern

**Screens:** any task that builds or revises a screen ID (AUD-03, POR-03, …) uses the `build-screen-from-handoff` skill,
plus `portal-screen` for the portal. Kits and templates use `ui-kit-component`; fixtures use `fixture-scenario`.
**Reference:** `docs/architecture/reference/frontend-feature.md`; layers in `docs/plan/04-frontend-architecture.md` §4.1.

## Layers (L0–L4; imports only point down)
- **L0 tokens and base** (`packages/ui/src/tokens`, styles): the only place colours, radii, shadows, type and motion are
  defined. Geist 400 and 500 only. Controls use `--radius-pill` (decided 2026-10-20).
- **L1 primitives and templates** (`packages/ui/src/{primitives,layout,overlays,feedback,…,templates}`): Radix for
  behaviour only, styled entirely with tokens, `forceState` on every interactive component.
- **L2 composite kits** (`packages/ui/src/<kit>/`): generic data shapes in the kit's own `types.ts`; never API types,
  never API calls.
- **L3 domain** (`apps/web/src/domain/<area>/`): the only layer that calls the API, through `@abacus/api-client` query
  options and mutations; maps DTOs to L2 props; owns optimistic updates and Undo.
- **L4 screens and shells** (`apps/web/src/screens/<ID>/`, `shell/`): one route component per screen ID, composed from
  a template plus L2/L3.
- One export line per component in `packages/ui/src/index.ts`, sorted; specimens come from a separate entry so
  production never bundles fixtures.

## Rules
- Call the backend only through `packages/api-client` (generated); never `fetch` directly (ADR-011, 013). Invalidate by
  the generated `…QueryKey` after mutations.
- Capabilities come from the server: `/v1/me` and per-record `allowed_actions`, read through `useCan`, `useFlag` and
  `useEntitlement` (`<Can>`, `<FeatureGate>`). No role or flag logic elsewhere; the backend enforces.
- Agent text renders only through `AgentText` (and `AgentProse` segments): never a plain string child, never
  `dangerouslySetInnerHTML` (ADR-065; ESLint enforces).
- Status words only from `status.ts`, generated from the status vocabulary (blueprint §3.3.1).
- Routing: TanStack Router area subtrees, one lazy chunk per screen ID. A path segment when the template or record
  changes; a search param when the same template is filtered (`?segment=`, `?view=`); `?ov=<key>[:<arg>]` for an O2–O6
  overlay over the current page (at most one drawer plus one modal); O1 popovers and hover stay in local state.
- Every lettered artboard state is a fixture scenario (persona, clock, snapshot) with a test; states are data
  conditions, never an `st` prop. Relative dates read `useNow()`, never `Date.now()`.
- Handle empty, loading, partial, error and not-allowed states.
- Approve, Sign off, Release, Send, Post and Decide appear only on human controls, never on agent-owned ones; a control
  that opens a dialog ends in "…".
- Keyboard accessible and labelled; axe has 0 serious or critical violations; Playwright journeys run by `make e2e`.
- Tests: Vitest + Testing Library, network mocked through the generated client's `fetch`.
- UI-label rule: glossary terms in identifiers; UI labels use the handoff's copy verbatim. Product name "Accrued" in the
  firm app; the portal never shows it (ADR-133).

## Arriving later (use the current equivalent until then)
`useCan`/`useFlag`/`useEntitlement` and `?ov=` overlays (with F-05 and F-06), `status.ts` generated from the vocabulary
(F-05-T12, S1; today `packages/ui/src/status.tsx`), `useNow()` and fixture mode (F-04, S1–S4), `domain/<area>/`
folders (as each epic adds them; today screens use `@abacus/api-client/query` options directly, so new
code goes into `domain/<area>/` and old screens move there when touched).

## Routes (F-03-T17)
- The route tree is split by area: `apps/web/src/routes/root.tsx` (root, shell, `lazyScreen`, `useParam`), `routes/firm/<area>.tsx` mounted from `routes/firm/index.ts` in the bar's order, and `routes/portal.tsx`. `router.tsx` only assembles them.
- A new screen is a `lazyScreen(async () => (await import("../../screens/X")).X)` in its area file, so it builds as its own chunk; read path parameters with `useParam("name")`.

## The portal entry (P-08-T29; P-08-T07, DEC-59)
The client portal is a second Vite entry, not an area of the firm tree. To add a portal screen:
- **Entry and tree.** `apps/web/portal.html` → `src/entries/portal.tsx` → `src/routes/portal/index.tsx`
  (`portalTree`). Add one `page("/path", …)` there; the screen is a `lazy(...)` import so it is
  its own chunk (the portal's first load has its own budget). Paths sit at the origin root (no
  `/client` prefix); sign-in (`/sign-in`) and `/accept` are public, every other page goes through
  `Area`, which ensures the BFF session (`app-core/auth/bff.ts`) and returns to `/sign-in?return=`.
- **What it may import.** `src/portal/*`, `src/domain/portal/*`, `src/screens/POR-*`, `app-core`
  and `@abacus/ui`. Never `src/legacy`, firm shell code, firm `domain/*` hooks or the firm route
  tree: eslint L7 (INV-4) refuses it.
- **Data.** Portal read models only (`/v1/portal/*`, the `portal` module), through the generated
  client; the token is in memory (`bff.ts`), never in web storage.
- **Manifest.** The `por.ts` entry keeps `path: null` (manifest paths resolve in the firm tree,
  DEC-347) with `entry: true` when no designed link reaches it; status `fixture`, then `live`
  once the screen reads the served routes.
- **Fixtures.** `src/fixtures/install-portal.ts` answers each journey persona's portal routes;
  add the screen's handlers there as well as in its scenario file.
- **White label.** `pnpm build:portal` (tsc, `vite build --mode portal`,
  `scripts/portal-dist-check.mjs`: no firm chunk, no "Accrued", no fixture string in dist/portal;
  then the portal's bundle budget) and the L7 crawl.
- Then follow the `portal-screen` skill for branding, shells and the three widths.

## The return frame and the reduced portal shell (T-02-T35)

- **Return frame.** TAX-02, TAX-03, TXP-12, TAX-09 and TAX-12 sit inside `ReturnFrame` on T2
  `RecordCockpit`: the subbar (42), the return's tabsbar (44) and the sync chip. A new return tab
  adds its route under `/tax-returns/$returnId/…` and its tab entry; it never draws its own header.
  In the gallery the artboard passes `toolbar` so the cockpit draws `AppShell` (window parity).
- **Reduced portal shell.** A K-1-only person sees the `k1` shell (DEC-129). A portal screen
  that a K-1 recipient can reach reads `me.portal.shell` (and its `nav`) and draws only that; the
  fixture personas `nora-calloway` and `pell-street-member` exercise it (POR-13 a and c).

## A cockpit section canvas (A-05; A-05-T62)
An EBP or completion screen that lives in the AUD-02 cockpit exports `use<Name>Canvas(workItemId, options)` returning a `CockpitCanvas` (title, actions, controls, `state`, children) and a rail key (`ebp_07`, `completion_checklist`); AUD-02 composes it. The flag-off and walled states are the canvas's `state` (C-20). Register its fixture scenarios in `fixtures/screen-scenarios.ts` for `?screen=` journeys. Typed form values render in `text-doc-typed`; a row and a document region share the server's `match_id`.

## The gate-class registry (Home; I-01-T26)

A gate that waits on a person shows on HOME-01 and HOME-02 with no Home code change. Its owner registers it in the backend (`register_gate_source`; `docs/contracts/home-and-gates.md` §12). The web side has two places to look, `apps/web/src/domain/home/`:
- `gateClasses.ts`: the band order and each kind's glyph. A new **kind** (rare: DF-25's set) needs a glyph here. A new **subkind** of an existing kind needs nothing.
- `messages.ts`: `GATE_SUBKIND_TITLE` gives a subkind its words when the presenter gives no title. Add the handoff's words, or mark the line "undesigned (I-01 §5.5)"; otherwise `fallbackTitle` reads the name as words.

Never count gates in a component: read `GET /v1/human-gates/counts` (`total`, `bands`). A row is a link to where the gate is decided, never a decision control (INV-1). Add the persona's fixture row to `countEquality.test.ts` when a scenario adds gates.

## Search and the palette (SHL-02; C15 v1; P-02-T14)

The palette (`screens/SHL-02`, mounted by the toolbar while `search.palette` is on) reads
`POST /v1/search` and `/v1/search/recents` through the generated client only. A screen does not
search on its own: it makes its record findable in the backend (C15 §6) and, when a record route
loads, records it in Recent (`POST /v1/search/recents`; the server re-authorises). Search text
goes only in a POST body, never a URL, a query key's string form, a log or an analytics event.
A new group needs its label in `screens/SHL-02/copy.ts`; the server orders the groups. Walled rows
are absent with no count or hint (DEC-43). Fixture rows live in `fixtures/seed/shl02.ts`, the
states in `fixtures/scenarios/SHL-02.ts` (registered for `?screen=SHL-02&st=` journeys); the
specs are `e2e/screens/shl-02-palette.spec.ts`.

## Frozen contracts (P-07-T64, DEC-1054)

A frozen contract (`docs/contracts/*.md` with **frozen**, snapshot under `backend/tests/contracts/<family>/v<n>.json`) takes additions only. A rename, retype, newly required field or removed enum member ships the next version with overlap: `python -m abacus_tools.contracts --freeze <family> v<n+1>`, never an edit of the old snapshot.
