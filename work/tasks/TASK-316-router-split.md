---
id: TASK-316
title: "F-03-T17: router split into lazy area subtrees; DEC-123 keeps the 7px squares"
spec: SPEC-306
acceptance_criteria: [AC-1]
risk_zone: green
status: done
branch: task-316-router-split
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan
- `routes/root.tsx`: the root, the sign-in callback, the app shell, `lazyScreen` and `useParam`.
- `routes/firm/index.ts`: the 14 firm areas in the bar's order. Areas with screens today: home, engagements, knowledge, clients and settings. The rest are empty until their epics.
- `routes/portal.tsx`: the client portal, join, sign-up and accept pages.
- `router.tsx` only assembles the areas.
- Every screen loads lazily (54 chunks), and every URL is unchanged.
- Not done: moving the guards into `beforeLoad`. Today's guards are role checks inside screens; they move with P-01's `useCan`.
- The frontend-feature skill now documents the routes. DEC-123 records the founder keeping the 7px squares, superseding DEC-109.

## Definition of done
- [x] The router, App and Layout tests pass.
- [x] tsc and eslint pass.
- [x] The build emits one chunk per screen.
- [x] check-fast passes.

## Progress log
- 2026-10-21: area files that build child routes inline inside `addChildren([...])` collapse TanStack's registered route types to `any`, which silently untypes every `Link`. Each child is now its own `const`, as in the original. A probe (`keyof RegisteredRouter["routesByPath"]`) confirmed the paths are typed again. Remember: never create child routes inline.
