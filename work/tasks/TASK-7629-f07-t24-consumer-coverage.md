---
id: TASK-7629
title: F-07-T24 consumer-state coverage and handoff conflict review
plan_key: F-07-T24
spec: SPEC-652
acceptance_criteria: [F-07-T24]  # every consumer artboard maps to a kit prop or slot; each conflict resolved or DF row
risk_zone: green
status: in-review
branch: f07-t24-consumer-coverage
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Map WB-01 a–i, WB-02 a–h, WB-03 a–g, HOME-03 a–f, CLI-03 (§9.6.1) and TAX-11 A–E onto SPEC-652's
props or consumer slots; settle the T-board names, Sep 15 counts, TPL-14a and TPL-17e viewers and
the watermark copy.

## Plan
- `docs/design/f07-consumer-coverage.md` (new): the map and the conflict table.
- `packages/ui/src/tokens/DECISIONS.md`: five conflict-log rows.
- `docs/plan/09-decisions-adrs.md`: DF-43 (saved prompts in the Workbench) opened.
- `docs/product/decision-log.md`: DEC-4624.

## Progress log
- `2026-11-12` — Coverage mapped, conflicts recorded (DEC-4624, DF-43).
