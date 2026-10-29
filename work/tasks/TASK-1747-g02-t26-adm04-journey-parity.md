---
id: TASK-1747
title: G-02-T26 ADM-04 journey E2E and parity for ADM-04, ADM-06 and ADM-07 (fixture half)
spec: SPEC-349
acceptance_criteria: [AC-31]
risk_zone: green
status: in-review
epic: G-02
plan_key: G-02-T26
branch: s14-g02-t26
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Journey E2E and parity for ADM-04 and the fixture-only states. Acceptance (backlog row): "j01 2,
j01 8 and j14 7 pass on staging with INV-1 to INV-5 and axe by Fri May 14, 2027, and parity.json
shows all 27 artboards built here at Tier C, with ADM-04 c, f, ADM-06 i, j and ADM-07 d marked
fixture-only." This task does the fixture half; staging is the S11 lane's.

## Plan
- Parity: 27 `.window` entries (ADM-04 a–j, ADM-06 a–j, ADM-07 a–g), `BUILT_PLANNED` += the three
  screens, baselines cropped from the handoff, measured on `parity-screens`; locks where ≤ 3 %.
- Contracts: the three Parity tables carry the measured numbers, locks and fixture-only rows.
- Journey: J01's ADM-04 step through the real route (`SCREEN_SCENARIOS` registers ADM-04).
- Fix found by the journey's axe: the gate rows' "Not allowed" cell contrast.
- TASK-042 closed as superseded (QD-3). DEC-837.

## Progress log
- `2026-10-29` — All 27 measured (ADM-04 a 2.58 … d 24.05; ADM-06 e 2.84 … b 12.38; ADM-07 f 0.73
  … e 11.64). Locked ADM-04 a, b, e, h, i; ADM-06 e; ADM-07 a, b, f. J01 fixture 7 passed (4 fixme
  for later lanes), J14 fixture 4 passed, ADM-04 vitest 14, screen-scenarios 8.
- G-02-T21's 2026-10-27 locks on ADM-06/07 were never measured; most are just over 3 % and now
  read report-only (DEC-837).

## Handoff
- **Current state:** PR open, held for the batch.
- **Left:** the staging run of j01 2, j01 8 and j14 7 (after the batch deploy); revising the
  boards for the rows over 3 %.
