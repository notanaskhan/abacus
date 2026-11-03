---
id: TASK-3222
title: P-04-T61 Runbooks and skills (review-grammar runbook, backend-module skill, consumer notes)
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T61
branch: s26-p04-t61
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3222 · P-04-T61 · Runbooks and skills: review-grammar runbook, backend-module skill, consumer notes

**Epic:** P-04 · **Sprint:** S26 · **Type:** DOC · **Zone:** red · **Depends on:** P-04-T59 (on main, DEC-2065)

## Plan (red zone)
- Files: `docs/runbooks/review-grammar.md` (stale storms, projector rebuild, undo-window incidents, grant voids), index row in `docs/runbooks/README.md`; `.claude/skills/backend-module/SKILL.md` gains "Registering with the review grammar"; consumer notes in `docs/architecture/reference/review-slot-consumers.md` (A-04, A-05, A-06, A-07, T-01, T-02, T-04, I-01, P-09, P-10; P-04 §9 also names A-05 by its attribute-test work).
- No migrations, registry or flag edits.
- Tests: `backend/tests/unit/review/test_p04t61_docs.py` (each incident shape, each consumer row names a slot and a first kind, the skill section).
- Rollback: revert the commit (docs only).

## Acceptance
- [ ] Runbook rehearsed once on staging: **not done**. Staging deploys only at batch close; the rehearsal log says pending. Carry to the S26 close.
- [x] Each consumer note names the slot it registers and its first reviewable or decision kind. A-07 and T-02 have none registered yet; their rows say so and name the slot they will use.

## Progress log
- 2026-11-03: drafted runbook, notes and skill section from the code on the S26 stack (stale.py, gates.py, proposal_undo.py, reproject_human_gates). Test written, not run (end pass).
