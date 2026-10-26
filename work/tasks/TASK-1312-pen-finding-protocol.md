---
id: TASK-1312
title: Pen-finding protocol - docs/ops/pentests/README.md and the pen-finding skill (Q-03-T037)
spec: SPEC-045
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: Q-03
plan_key: Q-03-T037
branch: s10-q03-t037-pen-finding
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Every pen-test #1 finding follows one protocol from intake to closure: triage within 2 working
days with severity and owner, a fix PR, a regression test that fails on the pinned build, and
closure only on the tester's retest; results only, never client data.

## Plan
- `docs/ops/pentests/README.md`: intake (finding ids `PT<n>-<NN>`, the per-window findings table),
  triage (our severity beside the tester's, owner, lane: hotfix for criticals within 5 working
  days, the batch for highs by the window deadline), fix (one PR per finding), regression test
  (fails on the pinned SHA, passes on main, written under `ac-test-author`), retest and closure,
  records.
- `.claude/skills/pen-finding/SKILL.md`: the session procedure.
- Solo edition: "regression test by the non-author" becomes a separate `ac-test-author` session
  that never reads the fix (AMENDMENT-solo item 3).
- No code. Rollback: revert.

## Progress log
- 2026-10-26: written (build-first; checks at the end of the run).
