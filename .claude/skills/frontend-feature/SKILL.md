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
