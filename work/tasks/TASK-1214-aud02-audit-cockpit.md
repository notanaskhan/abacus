---
id: TASK-1214
title: AUD-02 audit cockpit — Source Documents canvas, Viewer dock tab, read-only v1 Agent tab with pause and DF-04 (A-01-T12)
spec: SPEC-330
acceptance_criteria: [AC-1, AC-15, AC-24, AC-26]
risk_zone: green
status: done
epic: A-01
plan_key: A-01-T12
branch: s8b-audits-ui
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Counts read 11 of 24 = 3 + 4 + 3 + 1 and no Run, Begin or Auto mode control renders without its capability."

## Plan
- `apps/web/src/screens/AUD-02/{index,copy,scenarios}.ts(x)`, `AUD-02.test.tsx`; `fixtures/scenarios/AUD-02.ts` (a–e, g).
- `domain/audits/DockViewer.tsx` (SHL-08 evidence variant on C4), `domain/audits/AgentActivityTab.tsx` (SPEC-027 activity, Pause agent menu, DF-04 from `data_boundary`), `isNotFound`.
- Fixtures: `seed/audit-cockpit.ts` (`failed` grammar for e), `seed/audits-index.ts` (file paths verbatim from the spec, `sort`), `handlers/audits.ts` (agent, activity, pause on Northwind).
- Route `/audits/$auditId` (`?section=&dock=&doc=`, SHL-14 overlay for Add).

## Progress log
- 2026-10-25: built; 18 AUD-02 tests pass (a–e, g, loading, 404, 11 of 24 footing, Missing first, Story 2.1 capability gating, Viewer on a row, DF-04, Story 2.3 pause, URL section, AVOID). Decisions in DEC-341. f is A-01-T31's, h A-09's, i K-04's.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-341 | Canvas, Viewer and v1 Agent tab as built; DF-04 source; manifest status | No |
