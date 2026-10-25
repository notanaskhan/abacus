---
id: TASK-5008
title: "WB-09 as the ?ov=run-trace overlay with Copy link"
spec: SPEC-318
acceptance_criteria: [AC-12]
risk_zone: amber
status: done
branch: task-5008-trace-overlay
worktree: agentwt
created: 2026-10-26
updated: 2026-10-26
---

## Plan keys
P-09-T10 (overlay registration, Copy link), P-09-T13 (deep links) (partial).

## Plan
- **`routes/firm/run-trace.tsx`:** registers `run-trace` as a drawer that loads the agents domain lazily. It's imported from `routes/firm/index.ts`, next to the viewer.
- **`domain/agents/links.ts`:** `RUN_TRACE_OVERLAY` and `traceLink()`.
- **`domain/agents/overlay.tsx`:** `useOpenTrace()`.
- **TraceDrawer:** gains a "Copy link" button.
- **AgentDock:** takes an optional `onTrace`. Without one it keeps its own drawer, because AUD-02 renders outside a router in its screen tests.
- **Rollback:** revert the PR.

## Notes
- A static import of the domain entry from the route added 19 KB to the firm's initial bundle (259 of 250 KB). The route therefore writes the key itself, and `overlay.test.tsx` keeps it equal to the domain's.

## Progress log
- overlay (2), AgentDock (4), spec318runs, AUD-02 and AUD-03: 35 tests pass.
- The bundle is 240.6 of 250 KB (main is 240.4).

## Definition of done
- [x] Web tsc, eslint and targeted tests pass; the bundle is within budget.
- [x] check-fast passes.
