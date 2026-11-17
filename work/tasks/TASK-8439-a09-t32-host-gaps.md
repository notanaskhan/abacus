---
id: TASK-8439
title: "A-09-T32: rest: AUD-02 h tie chip, AUD-01 g tag verbatim, SHL-18 f live"
spec: SPEC-658
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: s48r-host-gaps
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T32
---

## Objective
Close A-09-T32's host gaps against the artboards: AUD-02 h's Structure row tie chip "Balanced · 50,760,000"; AUD-01 g's tag "Component auditor" exactly as drawn; SHL-18 f's "Visible to Pruett & Lang LLP" from the thread's own anchor facts.

## Plan (green)
1. Rail rows gain an optional code-built chip (SectionState, SectionRow, AuditSectionRowOut; kit Phase.chip drawn as a Tag); the Structure provider computes it from the consolidation engine's level 1 (ties and total assets), none when it cannot run or does not tie.
2. AUD-01: one "Component auditor" tag per group audit with a component auditor; the undesigned "Group · N components" tag removed (Type already reads FS audit (group)).
3. Collaboration anchor facts carry shared_with; component_thread names the auditor's organisation; LiveCommentThread uses it.
4. Tests: kit chip, AUD-02 h chip, tie-chip unit, live shared thread.

## Progress log
- `2026-11-17` — Built (S48 rest, DEC-5427). ENG-03 g is a toggle only on the artboard (components are picked on AUD-32), so no component picker was owed. POR-23's page uploads, reader and fixtures are A-09-T36 (S49). Gates and tests run once at the S48 end pass (build first, test last).
