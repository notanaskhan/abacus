---
id: TASK-8703
title: "G-04-T17: Undesigned console sections composed from kits (Support sessions, Status, Support queue, Publications, Plan requests)"
spec: SPEC-680
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: g04-t17-console-sections
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: G-04-T17
---

## Objective
The console's five undesigned sections (G-04 §5.1) composed from the kits: Support sessions list, Status incidents with post and update/resolve sheets, Support queue drawer on ChatThread, Publications queue (Publish disabled with the reason on the drafter's own draft), Plan requests tile and tenant card; rendered from fixture scenarios in tests and from the live API in the signed-in console.

## Plan (green)
1. apps/web/src/console/sections/{copy.ts, SupportSessions.tsx, Status.tsx, SupportQueue.tsx, Publications.tsx, PlanRequestsCard.tsx, live.tsx, sections.test.tsx}.
2. fixtures/seed/console-sections.ts: facts from PLT-01b/d, SHL-05 a and ADM-14 f only.
3. ConsoleShell: LiveSections under a QueryClientProvider once signed in (console build imports neither firm app nor portal).
4. Review logged in packages/ui/src/tokens/DECISIONS.md; DEC-5701.

## Progress log
- `2026-11-19` — Built. Staging render waits on the batch deploy; the fixture-mode console (PLT-01 TenantConsole) still draws PLT-01's own artboards, the sections are covered by sections.test.tsx. Tests run at the S51 end pass. Gates and tests run once at the S51 end pass (build first, test last).
