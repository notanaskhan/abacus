---
id: TASK-8354
title: "A-08-T32: AUD-12 live (JE artboards): the JE test and its selected entries on the API"
spec: SPEC-657
acceptance_criteria: [AC-7]
risk_zone: green
status: in-review
branch: aud12-je-live
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-08-T32
---

## Objective
Spec section: A-08 fixture-to-live swap; handoff AUD-12 a. AUD-12 live (JE artboards): the JE test and its selected entries on the API.

## Plan (green)
1. `JeTestOut` gains the population card's facts (`population_source`, `period_start`, `period_end`, `post_close_through`), additive; `make generate`.
2. `screens/AUD-12/live.tsx` (`AUD12Live`): Population, Risk criteria (filter by criterion) and the selected entries (cursor pages) on `GET /v1/je-tests/{id}` and `/entries?selected=true`; the footer's selection sentence from `selection`.
3. `/audits/$auditId/je-tests/$jeTestId`; Raise exception… opens SHL-15 on the test (`links.exceptionOverlay`), Expand testing… opens AUD-11 on the work item (`links.samplingOverlay`). The manifest gives AUD-12 its path; the gallery keeps a to h.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. tsc, eslint and the AUD-12 and route tests (80) clean. Partial: per-entry test results (no read yet, rows show Not started), the attributes card and the Viewer dock beside it, the grid artboards b, c, h live, a live-screen test, the source label as the ledger's code word. Gates and
  tests run once at the S47 end pass (build first, test last).
