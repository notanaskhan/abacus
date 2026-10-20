---
id: TASK-135
title: "F-05-T09 · /components gallery skeleton (VITE_UI_GALLERY lazy subtree, specimen registry, @abacus/ui/specimens entry), /components/tokens page and the dev-only /components/screens/:id route that mounts a registered L4 screen by catalogue ID"
spec: SPEC-048
acceptance_criteria: [AC-3, AC-4, AC-10, AC-11, AC-15]
risk_zone: green
status: todo
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
- [ ] Plan written in this file (required for amber and red)

Steps:
1. [ ] Verify Gallery.tsx and router.tsx:313-343; move routes under /components
2. [ ] Add the build-time switch and lazy subtree
3. [ ] Build the tokens page from tokens.ts
4. [ ] Add the screens/:id route and Not built state
5. [ ] Add a dist scan for gallery/fixture/Brightwater strings

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
- [ ] All listed ACs have passing tests or checks that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] No secrets or real client data committed (public repo)
- [ ] No new dependencies, or each one listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation (N/A for this task unless it adds either)
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals (N/A unless it adds any)
- [ ] Module README and relevant docs updated
- [ ] Decisions below recorded; ADR raised where needed

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

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | yes / no |

## Gotchas and discoveries
- 

## Questions for the human
- [ ] 

## Handoff
- **Current state:** not started
- **Exact next step:** step 1 of the plan
- **Uncommitted or partial work:** none
- **Known failing checks:** none
- **Open issues:** none
