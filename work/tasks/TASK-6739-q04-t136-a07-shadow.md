---
id: TASK-6739
title: "Q-04-T136: A-07 dark code shadowed on PF-X1's Northwind against its own tool; the T-04 1040 workspace shadow plan"
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
epic: Q-04
risk_zone: red
status: in-review
branch: s35b-q04-t136
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-11
updated: 2026-11-11
plan_key: Q-04-T136
---

## Objective
Each audit firm has one shadowed engagement with a recorded comparison against its own tool.
Synthetic (PF-X1, DEC-4100): the only audit firm is Brightwater Hale.

## Plan
- `assurance/shadow.py` (new; exported as `a07_shadow_facts`): read-only facts the dark A-07 code
  computes for one engagement. These are G5 to G7, the also-required list, the release (in-app or
  recorded), the AU-C 230 date and the archive (in-app lock or recorded). It writes nothing.
- `abacus_tools/a07_shadow.py` + `make a07-shadow`: the comparison against a firm-tool file, as
  Markdown for the go-live dossier.
- `docs/ops/pilot/pf-x1/a07-shadow.md` and `a07-shadow-firm-tool.yaml`: how the shadow works,
  PF-X1's firm-tool record, and the T-04 1040 workspace shadow plan from Tue Mar 21, 2028 (per
  tax firm: enrol, flags in draft mode, weekly comparison against the engine, exit at the
  deadline).
- Tests: `tests/unit/test_q04t136_a07_shadow.py`.
- Rollback: revert; nothing is written by the shadow.

## Partials (flagged)
- Synthetic only: PF-X1's "own tool" record is typed from the design's dates. A real firm's
  champion types theirs. The run itself is recorded at the end pass, on the loaded tenant.
- The T-04 plan is a plan: it runs in the season (Mar 21 to Apr 15, 2028), and the CCH
  comparison needs the engine's return.

## Progress log
- `2026-11-11` — Built; the compare's unit tests pass (4). The PF-X1 run is at the end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3305 | How A-07 shadows: external mode, read-only facts, a dated comparison against the firm tool's file | no |
