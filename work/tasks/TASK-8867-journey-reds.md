---
id: TASK-8867
title: "S52: Pre-existing fixture journey reds (J10 3, J16 8, J20 2/5/6/7/8)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: journey-reds
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-21
updated: 2026-11-21
plan_key: S52
---

## Objective
Fix the fixture-mode journey reds carried from DEC-5863 by fixing the screens and fixtures, not the tests (P-09 j03 6 checked too).

## Done
- J20 2: AUD-32's missing-TB row text ink-3, not ink-4 (axe contrast)
- J20 5/6: AUD-34 and AUD-35 artboards carry the data-artboard wrapper (as AUD-12)
- J20 7: POR-23 b's portal user chip is named Account while the person's name loads (axe button-name)
- J20 8: SHL-23 registered in the gallery (states full, 1-7; it never was, so today.spec's SHL-23 cases could not pass either); the journey opens SHL-23 5 on its artboard and opens the Late band
- today.spec: HOME-05 artboard follows the route (HOME-01 alone with today_brief.enabled off, f); SHL-23 2 opens on the Ridgeline drill-in (TodayPaneLive initialDrill)
- J10 3: POR-11 scenarios answer the portal binders list with Copperleaf's August close binder, and the artboard mounts under the firm's brand as PortalRoot does
- J16 8: CLS-01's client cell is the row's link to CLS-02 (handoff link graph), through onOpen
- P-09 j03 6: no change; it is test.fail (expected failure) and the list reporter prints the expected-failed attempt with an x, it is not in the failed count

## Progress log
- `2026-11-21` — Fixed and run locally: J10, J16, J20, p09 (34 passed, 4 skipped), today.spec + inv.spec (21), tier-d-today (5), vitest web 964 and ui layout 97. DEC-5864.
