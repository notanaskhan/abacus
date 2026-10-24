---
id: TASK-1127
title: ENG-02 remaining — CAS variant a, Work items tab, Team tab host, R2 tabs and gear planned and hidden in production, f and g fixture-only (P-07-T28)
spec: SPEC-321
acceptance_criteria: [AC-24]
risk_zone: green
status: done
epic: P-07
plan_key: P-07-T28
branch: s7-p07-tests-fe
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Scenarios a, f and g render in fixture builds and the production build shows only the live tabs."
Contract `docs/screens/ENG-02.md`; handoff `ENG-02 Engagement record/` (revision R2 wins).

## Plan
- Fixtures: Copperleaf record (a, g) with its 12 closes and team; Granite Peak at Oct 6 (f, an
  extra record only f's handlers carry); `GET …/team` handler; scenarios a, f, g with TABS.
- Screen: R2 tabs (planned ones only where PLANNED_VISIBLE), the gear, Team host, planned hosts,
  close discs and "7 of 12", the SKE note; gallery opens each state on its tab.
- Tests: ENG-02.test.tsx (a, f, g, R2 tabs, gear, Team, acceptance bullets),
  ENG-02.production.test.tsx (PLANNED_VISIBLE false), e2e axe for a, f, g.

## Progress log
- 2026-10-24: built; ENG-02 26 Vitest cases (2 production), e2e axe 8 states green; whole
  `apps/web` Vitest 140 files green. **Partial:** "On hold with reason" is not built — no hold route
  exists (P-07-T15 did not land it; DEC-272); a's stat rows, RunCard, Year-end and Related groups
  wait for C-01's close provider; f's ENG-12 content is K-04's.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-272 | The R2 tabs, the hosts and what waits | No |
