---
id: TASK-948
title: Portal build entry and shell data, portal fixtures, POR-01 sign-in part 1 (P-08-T07, T08, T09)
spec: SPEC-320
acceptance_criteria: [AC-6, AC-7, AC-8, AC-14, AC-15]
risk_zone: amber
status: done
epic: P-08
plan_key: P-08-T07; P-08-T08; P-08-T09
branch: TASK-948-portal-entry-por01-sign-in
created: 2026-10-23
updated: 2026-10-23
---

## Objective
- **P-08-T07 (amber):** the client portal as its own build: `apps/web/portal.html`,
  `src/entries/portal.tsx`, the portal route tree, `vite build --mode portal` into `dist/portal`
  with the portal CSP and a `build:portal` script, the branding loader for the tab's title and
  icon, PortalToolbarData and the EntitySwitcher from `/v1/me` → `portal`. Acceptance: "vite build
  --mode portal emits dist/portal with no firm chunk, no Accrued string and no fixture string, and
  the toolbar shows Approvals only for entity scopes."
- **P-08-T08:** TS seed rows and fixture handlers for the portal routes; POR-01 a–g with c′ and
  390, POR-02 a–f and M; personas tess-moreno and marisol-vega; footing tests.
- **P-08-T09:** POR-01 a, b, e, f, g, the role-routed landing and the 390 layout on the F-05
  AuthCard. Acceptance: "Scenario tests for a, b, e, f and g pass, no password field exists, and
  keyboard and screen-reader paths complete sign-in in fixture mode."

## Plan (amber: written before building)
- **Files.** `portal.html`; `src/entries/portal.tsx` (client config, in-memory bearer, fixture
  install behind `VITE_FIXTURES`); `src/routes/portal/index.tsx` (`/sign-in`, `/accept`, `/`,
  `/documents`, role landings; no design-system import so the first load stays small);
  `src/portal/{PortalRoot,PortalShell,EntitySwitcher}.tsx`; `src/app-core/{portal-contracts,
  portal-session}.ts`; `src/domain/portal/*`; `src/screens/POR-01/*`; fixtures; `vite.config.ts`
  (`--mode portal`: `portal.html` input, `dist/portal`, CSP connect-src self only, no gallery);
  `package.json` `build:portal`; `scripts/portal-dist-check.mjs`.
- **No migrations, registry, matrix or flag edits; no backend change.** The pre-session routes are
  unserved (DEC-139): drafts in `app-core/portal-contracts.ts`, recorded in the screen contract.
- **Tests.** POR-01 scenario and acceptance tests; portal shell (Approvals only for entity
  scopes), branding loader and fragment tests; footing tests; the dist check's rules; the budget
  script for a portal-only build; Playwright POR-01 at 1400, 720 and 390 with axe and a
  white-label scan.
- **Rollback.** The portal entry is a separate build no deployment serves yet; reverting the
  commit removes it. The firm build is unchanged (its CSP literal, budgets and tests hold).

## What changed
- **packages/ui** AuthCard `brand="header"` (the mark and firm name centred inside a left-aligned
  card, POR-01) and a neutral `tile` tone (e's clock); CodeInput `invalid` (red-ink inset ring,
  `aria-invalid`, `describedBy`) and `compact` (42 × 50 at 390). Tests in `auth-card.test.tsx`.
- **Portal entry (T07)** as planned. First load 105.5 KB of 150 KB; POR-01 adds 90.4 KB of 120 KB
  (`bundle-budget.mjs dist/portal`; the script now measures a portal-only build's routes against
  the portal's initial load). `portal-dist-check.mjs`: 9 files clean — no firm chunk, no fixture
  string, and the product's name only as the opt-in footer wordmark's label (gap recorded).
- **Firm app** `api.ts`: a 401 from `/v1/portal/auth/*` (a wrong code) no longer signs the firm
  user out; it is not a session ending.
- **Fixtures (T08)** `fixtures/handlers/portal.ts` (branding, start/verify/resend with per-challenge
  tries, renew, invitation preview, `/v1/me` with `portal`, the home), `seed/portal-home.ts`,
  `scenarios/POR-01.ts` (a, b, c, c2, d, e, f, g, M), `scenarios/POR-02.ts` (a, b, c, d, e, f, M),
  `install-portal.ts`, personas Tess Moreno, Marisol Vega and Meera Shah in `seed/portal.ts`,
  `portal.foot.test.ts`.
- **POR-01 (T09)** `screens/POR-01/` (21 tests), gallery `/components/screens/POR-01?st=a|b|e|f|g|M`,
  manifest `fixture`, `e2e/screens/POR-01.spec.ts` (18 passed locally).
- **Contracts** `docs/screens/POR-01.md` (status, non-artboard copy written, seven open gaps),
  `docs/screens/POR-02.md` (scenario status).

## Not done here (recorded)
- POR-01 c, c′ and d are P-08-T19's (their scenarios exist; an owner's code reaches a placeholder
  "Two-step verification" card, "Not built yet" in fixture builds).
- POR-02 g and h scenarios wait for their epochs (R2 waves 6, 7); the POR-02 screen is T15's.
- Legacy client screens are not mounted in the portal entry: the INV-4 lint forbids importing
  `src/legacy` from portal code; they stay at `/client/*` in the firm bundle until R-01/P-08-T28.
- Refresh, CSRF and sign-out (`app-core/auth/bff.ts`) are P-08-T11's.

## Checks
`apps/web` tsc (no new errors), eslint, prettier, vitest (119 files, 1179 tests); `packages/ui`
vitest and eslint; `vite build --mode portal` + `portal-dist-check` + `bundle-budget dist/portal`;
firm `vite build` + `bundle-budget dist` (44 met); Playwright POR-01 18/18; `make
check-generated`; `secrets_scan`; `scope_guards`.

## Progress log
- 2026-10-23: built T07, T08 and T09 in one change; moved the portal's design system out of the
  first load to meet its 150 KB budget; recorded the gaps in the POR-01 contract.
