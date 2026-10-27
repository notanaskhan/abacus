---
id: TASK-1429
title: HOME-01 main region on T11 (I-01-T06)
spec: SPEC-313
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: I-01
plan_key: I-01-T06
branch: s11-home
created: 2026-10-27
updated: 2026-10-27
---

## Objective
HOME-01's subbar (greeting, date, "Open Today" slot, the five-option Home segmented with the
Approvals count), tile row, and Waiting on you (summary, bands, 44 rows with glyph and due chips),
quiet day f and loading g. The badge, the header and the summary read one count source; no row
renders a gate verb.

## Plan
- `packages/ui` T11 `DashboardLayout`: `bare` (inside the app shell), `subbar` slot, the queue's
  `action` slot; the loading rows carry `aria-busy`.
- `domain/home/{gateClasses,messages,queries,WaitingOnYou,HomeSegmented,index}`.
- `screens/HOME-01/{index,copy,scenarios,HOME-01.test}.tsx`; gallery artboard; `/home` behind
  `home.dashboard` (legacy landing otherwise), lazy (its own chunk); manifest `fixture`.
- The right column draws the deadlines the read model carries; client activity is I-01-T12's.
- Tests: `HOME-01.test.tsx` (a, f, g acceptance; b-e, h, i, office-denver, today-brief-off,
  walled; segmented rule; AVOID). Axe and Playwright not run in this lane.

## Progress log
- 2026-10-27: built.
- 2026-10-27: targeted pass green (backend pytest -n 2 on the new and directly covering files, vitest on the touched FE files); gates clean (ruff, pyright, lint-imports, quality tools, check-heads, check-generated, tsc, eslint, prettier, vite build, bundle budget 245.9 of 250 KB). Playwright and axe-in-browser not run in this lane.
