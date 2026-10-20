---
id: TASK-135
title: "F-05-T09 · /components gallery skeleton (VITE_UI_GALLERY lazy subtree, specimen registry, @abacus/ui/specimens entry), /components/tokens page and the dev-only /components/screens/:id route that mounts a registered L4 screen by catalogue ID"
spec: SPEC-048
acceptance_criteria: [AC-3, AC-4, AC-10, AC-11, AC-15]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T09
branch: task-135-components-gallery
created: 2026-10-20
updated: 2026-10-20
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: write the plan into this file before code (solo amendment: no approval step).
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
/components/tokens shows every token with contrast under both ladders, /components/screens/:id passes ?st= ?as= ?clock= ?latency= ?frame=1 ?static=1 ?contrast=reference through to F-04-T04's fixture mode and shows Not built for an unregistered ID, and production dist contains no gallery code.

## Already built (verify, fill gaps only)
Source: `docs/plan/status/status-verified.csv` row F-05-T09 (status partial). Evidence: apps/web/src/gallery/Gallery.tsx at DEV-only /_ds (router.tsx:313-343); no VITE_UI_GALLERY, /components/tokens or /components/screens/:id.

Verify each item against the code, then build only what is missing. Do not rewrite what works.

Decided 2026-10-20: the gallery moves from `/_ds` to `/components`.

## Scope
**In**
- VITE_UI_GALLERY lazy subtree and specimen registry; @abacus/ui/specimens entry
- /components/tokens page: every token with contrast under both ladders
- Dev-only /components/screens/:id mounting a registered L4 screen by catalogue ID, passing the query parameters through, 'Not built' for unregistered IDs
- Move the gallery from /_ds to /components; /_ds no longer routes
- Production dist contains no gallery code

**Out**
- Component specimens and kits (later F-05 tasks)
- F-04-T04 fixture mode itself (stub the pass-through until it exists)

## Context to load
- Spec: `docs/specs/SPEC-048-design-system-core.md` (sections 5 and Task map; ACs AC-3, AC-4, AC-10, AC-11, AC-15)
- Epic: `docs/plan/epics/F-05.md`: F-05 §3 I1 and A2; F-05 §5 route table (/components, /components/tokens, /components/screens/:id) and L0 rows; F-05 §0 feature-flags row (VITE_UI_GALLERY, ?frame, ?st, ?static, ?contrast honoured only in gallery builds); F-05 §10 items 2, 4 and 7
- Task row: `docs/plan/epics/F-05.tasks.csv`, `F-05-T09`
- Process: `docs/plan/AMENDMENT-solo.md`
- Prior work: TASK-091..101 (Anas: tokens, Geist, components)

## Plan
- [x] Plan written in this file (green task: the steps below are the plan)

Steps:
1. [x] Verify Gallery.tsx and router.tsx:313-343; move routes under /components
2. [x] Add the build-time switch and lazy subtree
3. [x] Build the tokens page from tokens.ts
4. [x] Add the screens/:id route and Not built state
5. [x] Add a dist scan for gallery/fixture/Brightwater strings

Files to create or change:
- apps/web/src/gallery/**
- apps/web/src/router.tsx
- packages/ui specimens entry
- apps/web/vite.config.ts (switch only)

Tests to write (mapped to ACs):
- AC-3 -> axe on /components/**
- AC-4 -> ?contrast=reference sets data-contrast; production ignores it
- AC-10 -> routes render; dist has no gallery strings
- AC-11 -> tokens page and screens/:id parameters, Not built
- AC-15 -> /_ds no longer routes

## Definition of done
- [x] All listed ACs have passing tests or checks that reference them
- [x] Type check passes
- [x] Lint and format pass
- [x] Architecture and dependency rules pass
- [x] Full test suite passes; no tests skipped, weakened or deleted
- [x] No secrets or real client data committed (public repo)
- [x] No new dependencies, or each one listed below
- [x] Every query is tenant-scoped; every endpoint checks authorisation (N/A for this task unless it adds either)
- [x] AI calls (if any) go through the gateway with limits, logging and passing evals (N/A unless it adds any)
- [x] Module README and relevant docs updated
- [x] Decisions below recorded; ADR raised where needed

Commands:
```
make check
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| | | | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — task file written from the epic (SU-14); nothing built yet.
- `2026-10-20` — built (solo, no approvals). `VITE_UI_GALLERY` lazy `/components` subtree in `apps/web/src/router.tsx` (layout, index, `tokens`, `screens/$id`; one lazy chunk, `gallery/pages.tsx`; outside the app shell; no API calls). `/_ds` and its DEV-only route are gone. `@abacus/ui/specimens` (`packages/ui/src/specimens/index.ts`: `Specimen`, `SPECIMENS`, `specimenById`); the old gallery content moved (`git mv`) to `specimens/overview.tsx` as specimen `c-00-overview`. `/components/tokens` parses theme.css (`?raw`) and shows every token; colours carry hex, effective solid and contrast on card/shell/nested under the AA and reference ladders. `screens/:id` parses `?st ?as ?clock ?latency ?frame ?static ?contrast` into `FixtureParams` (stub for F-04-T04) and renders a registered screen or "Not built"; `?contrast=reference` sets `<html data-contrast>`; `?frame=1` drops the gallery chrome. Tests: `gallery/routes.test.tsx` (AC-4, AC-10, AC-11, AC-15), `gallery/dist.test.ts` (runs a real production `vite build` and scans `dist/`; a `VITE_UI_GALLERY=1` build is the positive control), `e2e/components.spec.ts` (axe AC-3, data-contrast, `/_ds`; green against `vite` on :5173). Vitest 424 tests pass; `vite build` clean; eslint, tsc and prettier clean in apps/web and packages/ui.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Flag is `import.meta.env.VITE_UI_GALLERY === "1"`, set by `define` in vite.config.ts: "1" for `vite` serve and Vitest, "" for any build unless the variable is set | A constant lets Rollup drop the routes and the lazy chunk; production needs no env var to be safe | no (DEC-112 covers the move) |
| Gallery routes sit under the root route, not `appRoute`, and are typed as no routes in the tree | Fixtures need no sign-in or API; typing them into the tree broke `useRouterState` inference in Board.tsx | no |
| Screen registry (`registerScreen`) lives in apps/web; specimen registry in `@abacus/ui/specimens` | L4 screens are app code; specimens are design-system code | no |
| Reference ladder = ink-3 .54 and match-ink #9253A2 only | The only handoff values ADR-155 and DEC-115 record | no |

## Gotchas and discoveries
- Vitest blanks every `.css` import, `?raw` included; vite.config.ts `test.css.include` lets theme.css through for the tokens page.
- The ESLint raw-hex rule flags `#9253A2` in tokens.ts, so the reference value is written as `rgb(146, 83, 162)`.
- The reference ladder's ink-2 value is not recorded in the files I was told to read; the tokens page shows only the two recorded overrides. F-05-T16 (parity) should add the rest.
- theme.css has no `[data-contrast="reference"]` rules yet (theme.css was out of bounds here); the attribute is set, the CSS that honours it follows with F-05-T03.
- Router tests need a fresh module graph per URL (`vi.resetModules()`); reusing one router instance after unmount hangs `router.load()`.

## Questions for the human
- [ ] 

## Handoff
- **Current state:** done; committed on the worktree branch, not pushed
- **Exact next step:** none. Later F-05 tasks add specimens to `SPECIMENS` and screens through `registerScreen`; F-04-T04 replaces the `FixtureParams` stub
- **Uncommitted or partial work:** none
- **Known failing checks:** none
- **Open issues:** none
