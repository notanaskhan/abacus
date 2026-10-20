---
id: SPEC-048
title: "Accrued design system, setup tier (F-05 sprint 0): tokens, AA ladder, self-hosted fonts, base CSS, lint rules, /components gallery skeleton"
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-011, ADR-078, ADR-089]
related_specs: [SPEC-016]
created: 2026-10-20
updated: 2026-10-20
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - Solo edition (`docs/plan/AMENDMENT-solo.md`): no owners, approvers or reservation issues; write acceptance tests first from this spec; amber and red tasks write their plan into the task file before code.

## 1. Summary
This is the sprint-0 slice of epic F-05 (`docs/plan/epics/F-05.md`): rows F-05-T01 to T09 of `F-05.tasks.csv`. It lays the Accrued design-system foundation that every screen epic builds on: one token source, the AA ink ladder, self-hosted fonts, base/motion/utility CSS, ESLint and compiled-CSS rules that fail off-system styling, and the `/components` gallery skeleton with the tokens page.

Anas already shipped part of this in TASK-091..101 (tokens, Geist, components). This spec asks the sessions to verify what exists and fill gaps only. Primitives, formatting, status, shell, overlays and templates (F-05-T10 onward) are later specs.

## 2. Problem and context
- Without one token source, screens drift from the palette. `packages/ui/src/theme.css` is a plain `@theme` with no `tokens.ts` to prove it against.
- Secondary text and focus rings need the DEC-11 AA ladder; there is no `contrast.css` and no reference mode.
- Fonts are Fontsource Geist already (no googleapis); Arimo and Gelasio for documents are missing.
- The gallery is a DEV-only page at `/_ds`; the plan has it at `/components` behind a build-time switch.
- Epic §3 stories A1 to A4, I1 and J1 are the source of the criteria below.

**Decisions taken 2026-10-20 (builder, plan's proposed option or explicit):**
1. Controls use pills (`--radius-pill`). Anas's 7px squared controls revert in F-05-T14 (not in this spec).
2. The gallery moves from `/_ds` to `/components` (F-05-T09).
3. F-05-T06 (codemod DS-06) runs only as a check for leftover Atelier classes, because the theme swap is done.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Builder | Writes tokens, CSS, lint rules, gallery; runs the gates |
| Screen developer (a later session) | Consumes tokens and is refused off-system styles by lint |
| Reader with low vision (Hannah Leclerc persona) | Needs AA-legible secondary text |
| Reader on a strict network (Claire Feld persona) | Needs fonts served from the firm's own host |

## 4. Goals and non-goals
**Goals**
- One `tokens.ts` that `theme.css` and `root.css` equal exactly; Tailwind namespaces reset so only Accrued tokens compile.
- The AA ladder and a `?contrast=reference` mode in gallery builds.
- Fonts self-hosted; CSP unchanged.
- Lint and compiled-CSS rules that reject drift.
- `/components` gallery skeleton and `/components/tokens`.

**Non-goals**
- Primitives, `format.ts`, status runtime, icons, shell, overlays, toasts, templates (F-05-T10 onward).
- Reverting 7px controls (F-05-T14), Atelier retirement from `package.json` (F-05-T34), legacy re-skin (F-05-T23).
- Dark mode (not planned, DEC-15); firm layout below 1280 px.
- Parity harness (F-05-T16), CI frontend job (F-05-T17).

## 5. User stories and acceptance criteria
Strings and numbers are the epic's (`F-05.md` §3 and `F-05.tasks.csv`).

### Story 1: one token source (epic A1)
- **AC-1** Given `packages/ui/src/tokens/tokens.ts` lists every value in design-foundations §1 (9 surfaces, 7 inks, 5 dark fills, 3 status families with hovers, clay, 8 match, 8 viz, 10 doc, 22 type roles, 13 radii, 14 shadows, 3 scrims, motion, z-index, about 25 layout sizes), when `tokens.test.ts` parses `theme.css` and `root.css`, then every value is exactly equal.
- **AC-2** Given a probe file using `bg-red-500 text-sm shadow-lg font-bold rounded-lg`, when Tailwind compiles, then it emits no rules; `bg-green-tint text-body shadow-e2 rounded-pane` emit exactly the token values (namespaces reset with `initial`).
- **AC-14** Given the radii, then `--radius-pill` (999px) is a token in `tokens.ts` and `theme.css`, and is the radius controls will use (decision 1).

### Story 2: readable secondary text (epic A2, DEC-11)
- **AC-3** Given the AA ladder (ink-2 text .70, ink-3 text .66, match text `#7E4590`, focus outline `2px solid rgba(43,31,23,.55)`), when axe runs on `/components/**` without `?contrast=reference`, then there are 0 serious or critical findings, and SPEC-016 AC-10 is not weakened.
- **AC-4** Given `?contrast=reference` in a gallery build, when the page renders, then `<html data-contrast="reference">` restores the handoff ladder exactly; production builds ignore the parameter.

### Story 3: off-system styling fails CI (epic A3, J1)
- **AC-5** Given the new rules (palette regex that admits Accrued names, hex and `rgba(` ban in `packages/ui` outside `tokens/` and `brand/`, banned `font-semibold`/`text-lg`/`shadow-lg`, `toLocale*`/`Intl`/`toFixed` outside `format.ts`, `Date.now()` outside `clock.tsx`, the L1 brand strings), when a screen uses any of them, then ESLint fails. Lint rejects `bg-neutral-100`, `#7a4e12`, `font-semibold`, `text-lg`, `toLocaleDateString`, emoji and `Accrual` in screens, and accepts `bg-green-tint` and `text-red-ink`. The suite covers every accept and reject case without weakening `eslint-rules.test.ts`.
- **AC-6** Given a production build, when the compiled-CSS check scans `dist/*/assets/*.css`, then any 600/700 weight outside `[data-doc]` or any colour literal not in `tokens.ts` fails stage 1.
- **AC-9** Given F-05-T06 runs as a check (the theme swap is done), when it scans `apps/web/src`, then it reports no leftover `bg-surface`, numeric-spacing, `text-sm`/`text-xs`, `font-semibold` or border classes, and all 291 existing Vitest cases plus `e2e/journey.spec.ts` stay green with no test weakened.

### Story 4: fonts from the firm's own host (epic A4)
- **AC-7** Given Fontsource Geist and Geist Mono are preloaded and Arimo and Gelasio load only in document chunks, when any page loads, then no request goes to `fonts.googleapis.com` or `fonts.gstatic.com`, `document.fonts.check('500 13px Geist')` is true, and the `abacus-csp` meta in `apps/web/vite.config.ts` is unchanged.

### Story 5: base CSS (F-05-T05 acceptance)
- **AC-8** Given `base.css`, `motion.css` and `utilities.css` (hairline, pane, well, tabular, doc-scope) with reduced-motion and forced-colors blocks, when a page loads, then `body` computes to 13px/15.6px Geist with tabular numbers on `#F8F8F6`, and forced-colors keeps pane edges and the .55 focus outline.

### Story 6: gallery skeleton (epic I1; F-05-T09 acceptance)
- **AC-10** Given `VITE_UI_GALLERY=1`, then `/components`, `/components/tokens` and the dev-only `/components/screens/:id` render from fixtures with no API calls (the other `/components/*` routes in epic I1 are later tasks); given a production build, then CI finds no gallery, fixture or "Brightwater" strings in `dist/`.
- **AC-11** Given `/components/tokens`, then it shows every token with contrast under both ladders; and `/components/screens/:id` passes `?st=`, `?as=`, `?clock=`, `?latency=`, `?frame=1`, `?static=1`, `?contrast=reference` through to the fixture mode (F-04-T04; a minimal stub until it exists), and shows "Not built" for an unregistered ID.
- **AC-15** Given the DEV-only gallery at `/_ds`, when F-05-T09 lands, then it is served from `/components` and `/_ds` no longer routes.

### Story 7: governance and installs (F-05-T01, T02 acceptance)
- **AC-12** Given the design-system ADR P-03 (next free ADR number on `main`) is accepted and this SPEC-048 supersedes SPEC-016 section 4 (recorded in both files), then both exist before any token PR merges; `tokens/DECISIONS.md` is seeded with the conflict log.
- **AC-13** Given allowlist bundle #1 (Fontsource Geist, Geist Mono, Arimo, Gelasio; react-table; react-virtual; Radix overlay packages; `packages/ui` exports map), when it lands as one change touching `dependency-allowlist.yaml`, `package.json` and the lockfile (installed by the builder), then `check_dependencies` passes.

## Task map
| Plan key | Task | Acceptance criteria |
|---|---|---|
| F-05-T01 | TASK-127 | AC-12 |
| F-05-T02 | TASK-128 | AC-13 |
| F-05-T03 | TASK-129 | AC-1, AC-2, AC-3, AC-4, AC-14 |
| F-05-T04 | TASK-130 | AC-7 |
| F-05-T05 | TASK-131 | AC-8 |
| F-05-T06 | TASK-132 | AC-9 |
| F-05-T07 | TASK-133 | AC-5, AC-6 |
| F-05-T08 | TASK-134 | AC-5, AC-7 |
| F-05-T09 | TASK-135 | AC-3, AC-4, AC-10, AC-11, AC-15 |

## 6. Behaviour and flows
**Happy path**
1. Land the ADR and this spec (T01), then the allowlist bundle (T02).
2. Tokens (T03), then fonts (T04), base CSS (T05), the leftover-class check (T06) and lint (T07).
3. Tests for fonts and lint (T08); gallery skeleton and tokens page (T09).

**Alternate paths**
- A package version is too new for pnpm's minimum release age: pin an older exact version (epic R6).
- Fontsource names differ (`@fontsource/geist` vs `@fontsource/geist-sans`): confirm at install (epic Q5).

**State transitions:** N/A (no entity state).

## 7. Domain and data changes
N/A: front-end only. Invariants: `tokens.ts` is the only place a colour literal may live (outside `brand/`). No migrations, no retention.

## 8. Interfaces
No API. Public surface: `@abacus/ui` exports map (T02), `/components` routes (T09), query parameters in AC-4 and AC-11 honoured only in gallery and fixture builds.

## 9. Authorisation and tenancy
N/A: no data access. The gallery renders fixtures with no API calls and is absent from production builds (AC-10).

## 10. AI behaviour
N/A: no model calls.

## 11. Integrations
- **External systems:** npm registry for the allowlist bundle only. Fonts are bundled, no remote host.
- **Idempotency:** the codemod check (AC-9) is read-only.
- **Failure behaviour:** a failing lint or compiled-CSS check fails `make check`.

## 12. Edge cases and failure modes
- The three tests that assert visible "AI" text (`spec016.test.tsx` ac3, `spec021.test.tsx:142`, `spec035templates.test.tsx:61`) must stay green; do not edit them.
- Radix scroll-lock may inject a `<style>` under `style-src 'self'`; verify in a production build (epic R9).
- Anas's existing `theme.css` must be verified against `tokens.ts` rather than rewritten from scratch.
- Firm minimum width is 1280 (DEC-15); no reflow work here.

## 13. Security and privacy
- **Data classification:** public (CSS, fonts, fixtures). **PII involved:** none.
- **Secrets:** none. **Threats:** remote font hosts leaking viewer IPs; mitigated by AC-7 and the unchanged CSP.
- Fixtures must not contain real client data (public repo).

## 14. Audit trail and evidence integrity
N/A: no business actions. Design conflicts and parity deviations are logged in `tokens/DECISIONS.md`.

## 15. Observability
N/A beyond CI output. Bundle budgets (firm 250 KB, portal 150 KB, route chunk 120 KB gzip) are enforced by F-05-T17, not here.

## 16. Performance and scale
Geist and Geist Mono preload eagerly; Arimo and Gelasio load lazily in document chunks only.

## 17. UX
- **Screens:** `/components` index and `/components/tokens` (dev and fixture builds only).
- **States:** `/components/screens/:id` shows "Not built" for an unregistered ID.
- **Accessibility:** WCAG 2.2 AA with the DEC-11 ladder (AC-3); forced-colors keeps pane edges and focus outline (AC-8).

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 | unit | `tokens.test.ts` equality of `tokens.ts` with `theme.css` and `root.css` |
| AC-2 | unit | Tailwind compile of the probe file emits no rules; token utilities emit exact values |
| AC-3 | e2e | axe on `/components/**`, 0 serious or critical |
| AC-4 | e2e | `?contrast=reference` sets `data-contrast`; production ignores it |
| AC-5 | unit | `eslint-rules.test.ts` accept/reject cases (RuleTester) |
| AC-6 | unit | compiled-CSS check over a built fixture |
| AC-7 | e2e | request log has no Google Fonts hosts; `document.fonts.check`; CSP meta unchanged |
| AC-8 | e2e | computed styles of `body`; forced-colors emulation |
| AC-9 | script + unit | codemod check output empty; existing Vitest and journey e2e green |
| AC-10 | e2e + build | gallery routes render; `dist/` scan finds no gallery strings |
| AC-11 | e2e | tokens page lists tokens under both ladders; `:id` parameters and "Not built" |
| AC-12 | doc check | `validate_docs` passes; ADR and SPEC reference each other |
| AC-13 | tool | `check_dependencies` passes |
| AC-14 | unit | part of `tokens.test.ts` |
| AC-15 | e2e | `/components` renders; `/_ds` has no route |

## 19. Rollout
- **Feature flag:** none. `VITE_UI_GALLERY=1` is a build-time switch (epic §0).
- **Migration and backfill:** none. **Rollback:** revert the commit; no runtime state.

## 20. Open questions
None open. Answered with the plan's proposed option:
- Gallery on a private preview host? No: dev, fixture and opt-in preview builds only, never staging or production (epic Q1).
- Fontsource package names and Arimo licence text: confirm at install in T02 (epic Q5).

## 21. Future / explicitly deferred
- Primitives, pills and the 7px revert (F-05-T14); formatting, status, icons (T10 to T13).
- Parity harness and CI frontend job (T16, T17); accessibility harness (T24).
- Atelier dependency retirement (T34).
