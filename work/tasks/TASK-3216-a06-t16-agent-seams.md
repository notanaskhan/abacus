---
id: TASK-3216
title: A-06-T16 agent seams (why-surfaced number provenance, human-only A-06 decisions)
spec: SPEC-642
acceptance_criteria: [AC-11]
risk_zone: red
status: in-review
epic: A-06
plan_key: A-06-T16
branch: s26-a06-t16 (stacked on s26-a06-t15)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"Generated I-AGENT-NEVER tests deny agent and system principals on every A-06 decision action at
matrix, live-human and database layers, and a free number in why_surfaced is flagged Unsupported."

## Plan (red)
- `findings.record_finding`'s agent path (task_scope, C4-verified citations since A-06-T11) also
  checks number provenance. `NewFinding.figures` holds code's numbers; any other number in
  `why_surfaced` marks `evaluation.why_surfaced_support = unsupported` (dates, references and
  codes excluded).
- Migration 0661: `deficiency.concluded`, `sum.concluded` and `attribute_result.marked` join
  `abacus_human_only_actions()` (and the YAML and generated module). The downgrade restores 0569's
  list.
- Test: `tests/unit/assurance/test_a06t16_agent_seams.py`.

## Progress log
- 2026-11-03: built. Partial:
  - suggestion targets with appliers for deficiency severity and disclosure answers (the
    severity card's recommendation already rides C3's `recommended_option_key`; disclosure
    answers wait for A-06-T25's service);
  - the DET `fs_draft` run record (A-06-T25 drafts).
  Tests at the S26 end review.

## Decisions made during this task
DEC-2216.
