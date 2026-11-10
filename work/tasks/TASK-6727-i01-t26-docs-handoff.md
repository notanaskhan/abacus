---
id: TASK-6727
title: "I-01-T26: C13 v1 frozen, HOME-01/02 deviations, practice README home section, RB-70 home counts, gate-class skill note, consumer notes"
spec: SPEC-650
acceptance_criteria: [AC-29]
risk_zone: amber
status: in-review
branch: s35-i01-t26
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: I-01-T26
---

## Objective
A fresh session can register a new gate subkind and see it on Home using only the contract doc and the skill note.

## Plan (amber: written before the build)
- `docs/contracts/home-and-gates.md`: v1 frozen 2026-11-10; §12 "Registering a new gate subkind" (backend source, words, where it opens, the tests, what Home shows); §13 consumer notes to I-02, T-08, I-03, I-04 and W-02, plus the R2 bands.
- `docs/screens/HOME-01.md` DV-9 (h/i unlocked deviation) and DV-10 (mention text read-time, DEC-61), with the Parity row; `docs/screens/HOME-02.md` DV-9 (no new deviation; count equality).
- `backend/src/abacus/modules/practice/README.md`: a Home section.
- `docs/runbooks/RB-70-home-counts.md` (new: count mismatch, projector and activity rebuilds, `home.approvals` rollback) and its index row in `docs/runbooks/README.md` (next free number: RB-70, after RB-69 on main).
- `.claude/skills/frontend-feature/SKILL.md`: the gate-class registry note.

## Notes
- The runbook name follows the runbooks README rule (`RB-<nn>-<slug>.md`), not the row's `docs/runbooks/home-counts.md`.

## Progress log
- 2026-11-10: written; validate_docs at the end pass.
