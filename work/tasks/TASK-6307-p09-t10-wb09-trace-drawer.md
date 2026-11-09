---
id: TASK-6307
title: P-09-T10 WB-09 TraceDrawer, summary card, timeline grammar, a2 to a4, not-allowed, loading
spec: SPEC-648  # Stories 4.1 to 4.3; handoff WB-09
acceptance_criteria: [AC-1]
risk_zone: green
status: in-progress
epic: P-09
plan_key: P-09-T10
branch: s32-p09-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
Finish WB-09 over TASK-5008's `?ov=run-trace` overlay and Copy link: every artboard state.

## Plan
- New `domain/agents/TraceParts.tsx`: `SummaryCard` (Run #, agent, started with trigger, runs
  as, duration "so far" while live, records read, citations, writes "x done · y waiting", model,
  region, training), `Timeline` (marks by `mark`, durations, a v2 step row expands to the step
  route's arguments and first five records), `RecordsReadTable` (Source · Records · Through,
  Total), `WriteState` ("Waiting on ‹approver›"), `useMinimumLoading` + `TimelineSkeleton`.
- `TraceDrawer`: uses them; not-allowed state on 403/404; footer "Export trace (JSON)", "Download
  PDF" (disabled until P-09-T11), the 7-year note.
- Backend: `TraceRowOut.step_id` (additive) on v2 execute/compute rows.
- Fixtures: #4118's "Execute › list returns" step detail (a2).
- Tests: `domain/agents/TraceParts.test.tsx`.

## Progress log
- `2026-11-09` — Built; not type-checked or run (end pass). Carries a fix for P-09-T09's
  RunPane (StatusPill has no `muted` tone; `StatusTone` isn't exported): folded into #1499 at the
  restack.
- Partial: "Approve…" on a waiting write (SHL-10) needs the viewer's id against the approver,
  bound with the human intents in P-09-T14; c's "Open CCH Axcess Tax ›" waits for WB-11's overlay
  (W-01); the a2 samples are empty because the fixtures hold no TAX-02 records; PDF is P-09-T11.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3007 | Not-allowed on 403 and 404; skeleton floor; row expansion only for v2 tool rows with content | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status partial.
- `2026-11-09` — Partials round (branch s32p-p09-t10, DEC-3024): WB-09 a2 shows the first five
  returns read (TAX-02 seed, linking to each return) in fixtures. The connection name in "Records
  read" stays open: no firm-side connection lookup by id; needs a C6 `connection_label` resolved
  by the connections module (W-01).
- `2026-11-10` — Partials round 2 (branch s32q-p09-t10, DEC-3143): "Approve…" on a waiting proposal opens SHL-10. Still open: "Open CCH Axcess Tax" (WB-11, W-01), PDF (P-09-T11 is JSON only).
