---
id: TASK-6726
title: "I-01-T25: final proof: count equality on every surface for six personas, every subkind renders, h/i parity rows, j17 0, j16 A2, j19 7"
spec: SPEC-650
acceptance_criteria: [AC-7, AC-29]
risk_zone: green
status: in-review
branch: s35-i01-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: I-01-T25
---

## Objective
Counts are equal on every surface for every persona and J17's P0 core is walkable on staging by Fri Mar 3, 2028.

## Plan
- `apps/web/src/domain/home/countEquality.test.ts`: covers Daniel, Margaret, Samuel, Grace, Kevin and Hannah.
  - Each surface is checked through its own fixture path: the header and badge, HOME-02's band sums and rows, the summary line, and SHL-04's Approvals tab (`tabOptions` on the counts' total).
  - After a snooze and a reassignment the surfaces still agree, and Daniel's demo reads 11 = 3 + 6 + 2.
- `backend/tests/unit/test_i01t25_every_subkind_renders.py`: every registered gate source (all modules imported) has words, specific (`GATE_SUBKIND_TITLE`) or generic (snake_case read as words), and its kind draws a HOME glyph.
- `docs/design/parity-manifest.json`: `home-01h.window` and `home-01i.window` (Tier C, pinned sha256), recorded as deviations and unlocked. The bands are unwired until after Apr 20, 2028 (P-29 rule 2), so the full-window frames cannot match until the wiring; they lock then.
- Journeys:
  - `e2e/journeys/J17-practice-economics.spec.ts`: "j17 0: Margaret's Home tiles and counts tie (P0 core)".
  - J16: "j16 A2" (fixme until wiring and P-05's flags).
  - J19: "j19 7" (fixme until T-08's `amendment_approval`).

## Partials (flagged)
- **Count equality after a decision:** not covered. The fixture gate handlers have no decide path (a decision moves the gate in its owner's service); the snooze and reassignment cases stand in.
- **h/i parity:** the rows are not locked (see above).
- **Staging walk of j17 0:** happens after the S35 batch deploy.

## Progress log
- 2026-11-10: built; tests at the end pass.
