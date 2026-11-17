---
id: TASK-8420
title: "C-01-T40: CLS-10 flux screen"
spec: SPEC-655
acceptance_criteria: [AC-48, AC-49]
risk_zone: green
status: in-review
branch: c01-t40-cls10-flux
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T40
---

## Objective
Spec section: docs/plan/epics/C-01.md §5 CLS-10. CLS-10 Flux states a–e on T6: Issues, Adjustments and Flux control bar; comparison segmented with Budget disabled; variance cells; Explain streaming state; Accept for a Manager or Partner; commentary banner; year-over-year dashes; citations; Open in Excel.

## Plan (green)
1. `screens/CLS-10/{index.tsx,copy.ts,scenarios.ts,CLS-10.test.tsx}`: control bar, tally strip from the set's counts, basis segmented (Budget disabled), statement table formatted through format.ts (`amount` whole, `pct`), amber variance cell for unexplained over-both lines, agent drafts through AgentText with numbered citations per driver, Explain… (tracing line) and Accept gated by `flux.accept`, commentary banner, Open in Excel link.
2. Fixtures: `copperleafFluxAt(a|b|c)`, `copperleafFluxYoy`; handler serves mom and yoy; scenarios a–e plus `raj`.
3. Route `/closes/$closeId/flux` renders CLS-10 inside the close shell; manifest status fixture.
4. Screen contract `docs/screens/CLS-10.md`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack. tsc, eslint and prettier clean; vitest not run yet (end pass). Partial (DV-a to DV-e): no subtotal rows (not in FluxSetOut), no Adjustments count, SHL-08/SHL-09 not wired, the YoY note left out. Gates and tests run once at the S48 end pass (build first, test last).
