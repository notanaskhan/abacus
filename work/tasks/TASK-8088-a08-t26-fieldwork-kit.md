---
id: TASK-8088
title: "A-08-T26: Fieldwork L3 kit (apps/web/src/domain/audits/fieldwork) and its gallery board"
spec: SPEC-657
acceptance_criteria: [AC-1, AC-3, AC-6]
risk_zone: green
status: in-review
branch: a08-t26-fieldwork-kit
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T26
---

## Objective
The L3 kit AUD-12, AUD-13, AUD-14 and AUD-26 compose from, with every component state in the
gallery (axe clean, forced-colors focus rings through the design system's controls).

## Built
`apps/web/src/domain/audits/fieldwork/` (exported from `domain/audits`):
- `je.tsx`: BlockCard, CardWell, PopulationCard (the tie from the server), CriteriaTable (row
  click filters; "Not available from this ledger" with the missing fields), SelectedEntriesCard
  (pager, "Review in package →", pending-approval header; reasons always beside the score;
  weekend dates carry their day), AttributesCard (value chips are the only source links:
  `ValueChipLink` pins the MatchProvider match and lights the viewer region; agent notes through
  AgentText with the amber corner), TestingFooter (Adopt, Expand testing, Raise exception;
  "Waiting on Hannah Leclerc").
- `grid.tsx`: TestGrid (`details` and `controls` on A-05's grid grammar), DeviationLog (empty:
  "0 deviations · upper deviation limit 8.8% < tolerable 10%").
- `expand.tsx`: ExpandTestingSheet (O3; steppers, "Selected becomes 50", required rationale with
  the C-31 marker: the agent's draft fills the field only on Adopt; approver Picker; Request
  approval disabled until rationale and approver).
- `analytics.tsx`: AnalyticsTable (whole numbers, no dollar sign; unexplained over-threshold rows
  amber), RunRows.
- `confirmations.tsx`: ConfirmationDrawer (Response, Reconciliation with the reconciling items and
  the server's unreconciled figure, Classification, Why this was surfaced; Accept reconciliation
  only when `allowed_actions` has it), NewConfirmationSheet (Send disabled with the red helper
  until a non-client source is ticked; the server's 409 stays the gate).
- `ssars.tsx`: SsarsRail for review, compilation and preparation.
- Gallery: `apps/web/src/screens/kit-a08.tsx` registers `KIT-A08` (11 `?st=` states) on the
  handoff's figures (`kit-a08-data.ts`, `fixtures/seed/fieldwork.ts`); `kit-a08.test.tsx` 12 pass.

## Partial
- Axe and forced-colors run in the gallery e2e (end pass); the gallery axe job was red on main
  before S46.
- The viewer page in the gallery is a placeholder image (no server page images in fixtures); the
  lit region and its label are the handoff's.

## Progress log
- `2026-11-15` — Built; kit test 12 pass, lint and types clean.
- Lesson: gallery specimens may not import `domain/*` (feature-root rule); a domain kit's board
  lives one level under `src/screens/` and registers from `screens/gallery.tsx`.
