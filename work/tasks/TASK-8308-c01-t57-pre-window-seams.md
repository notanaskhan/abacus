---
id: TASK-8308
title: "C-01-T57: Pre-window live-path seams behind default-off flags"
spec: docs/plan/epics/C-01.md §4.7
acceptance_criteria: [C-01-T57]
risk_zone: green
status: in-review
branch: c01-t57-pre-window-seams
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: C-01-T57
---

## Objective
Pre-window live-path seams behind default-off flags.

## Plan (green)
1. `apps/web/src/app-core/close-seams.tsx`: `CloseSourceSeam` (SHL-08 viewer, SHL-12 signoff, SHL-10 approve close sources behind `closes.engine`), `PortalCloseIntakeSeam` (`/documents?period=` behind `closes.portal_requests`), `QuestionVariantSeam` (POR-04 variant e), `useCloseNavEntry`; each lazy-imports `close-seam-slots.tsx`.
2. The one change to each live file: `routes/firm/sheets-host.tsx` (signoff, approve), `routes/firm/viewer.tsx` (viewer), `routes/portal/index.tsx` (documents, request).
3. `app-core/close-seams.test.tsx`: the flag-off renders are byte-identical to today's.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5305). Prettier, eslint, tsc and the seam tests (6) clean while building. Gates and
  tests run once at the S47 end pass (build first, test last).
