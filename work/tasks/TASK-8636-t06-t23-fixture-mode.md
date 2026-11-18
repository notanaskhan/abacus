---
id: TASK-8636
title: "T-06-T23: Fixture mode for the eight T-06 screens (44 artboards)"
spec: SPEC-702
acceptance_criteria: [AC-19, AC-34]
risk_zone: green
status: in-review
branch: t06-t23-fixture-mode
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-06-T23
---

## Objective
Each of the 44 artboards of TXP-03, TXP-04, TXP-08, TXP-09, TXP-13, TAX-11, CLI-03 and AUD-38 opens from ?screen=<ID>&st=<state> in fixture mode without Docker, at its contract persona and demo clock.

## Plan (green)
1. apps/web/src/fixtures/scenarios/<ID>.ts for the eight screens, generated from the docs/screens artboard tables (persona, clock, scenario seed named per state); Ridgeline states read the T-05 entity workbook snapshot their seed stands on.
2. fixtures/screen-scenarios.ts registers them on the E0 shell with the T-06 flags (tax.entity_depth, tax.other_entity_workpapers, tax.form_preview, clients.relationship_map, tax.tb_handoff) and the Ridgeline return id.
3. fixtures/scenarios/t06-fixture-mode.test.ts: one scenario per contract artboard, 44 in all, each opens from its URL with a persona and a parseable clock.

## Progress log
- `2026-11-18` — Built in the S50 completion round (DEC-5636). Partial: the per-screen data handlers (register, basis, states, M-3/M-2, other-entity workpapers, form preview, relationships graph, TB hand-off) typed against the T-06-T05/T07/T08 stubs, exported from the Python scenario with make fixtures, join with each screen task; the Ridgeline depth figures are in T-06-T22's slice. AUD-38 d's contract clock gives only Oct 21, 2026, so the scenario uses 9:00 AM CT. TXP-04 a′ is keyed ap (its board file TXP-04ap.png). The DF-08 composed states arrive with T-06-T02's boards (blocked on design). Gates and tests run once at the S50 end pass (build first, test last).
