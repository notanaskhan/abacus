---
id: TASK-8035
title: "C-01-T33: CLS-01 Closes index states a–f on T1"
spec: SPEC-655
acceptance_criteria: [AC-1, AC-4, AC-5, AC-6]
risk_zone: green
status: in-review
branch: c01-t33-closes-index
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T33
---

## Objective
CLS-01 on T1: tiles that filter, split chips (Period, Status, Preparer, Reviewer, Attest),
search with "Showing n of 22", the reconciled bar, the running disc and popover line, the running
pill, the row menu (Open, Start run, View plan), Start run's confirm, loading and attest-empty,
the List · Board toggle hidden while `board.enabled` is off, and `scenarios.ts`.

## Plan
1. [x] `domain/closes` (`useCloses`, `useRunningCloses`, filters) over the generated client.
2. [x] `screens/CLS-01` (`index.tsx`, `copy.ts`, `scenarios.ts`, `CLS-01.test.tsx`) on
   `IndexList`; `fixtures/scenarios/CLS-01.ts` a–f on the figure book (C-01-T13).
3. [x] Route `/closes` (search params) in `routes/firm/closes.tsx`; the close shell's Back now
   links to it; `nav-areas.ts` marks Closes routed; manifest CLS-01 `fixture` at `/closes`.
4. [x] Contract: `CloseRowOut.client_id` (additive) so View plan opens CLS-09 by client; the
   service fills it; client regenerated.
5. [x] `docs/screens/CLS-01.md`.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029).
- `2026-11-15` — Built. Also tidied C-01-T13's fixtures for the web lint rules (no `toFixed`,
  numbers through `String`, no non-null assertions in its figure test). `tsc` and eslint clean on
  the touched files; vitest not run (end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| — | DV-a to DV-d recorded in the screen contract (DEC-5019, QC-7) | no |
