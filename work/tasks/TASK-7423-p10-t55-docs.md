---
id: TASK-7423
title: "P-10-T55: docs, runbooks and skills for runtime v2: SPEC-647 as built, ai-agent.md v2, threat model tool-use rows, agents/workbench/notifications READMEs, skill notes, consumer notes"
spec: SPEC-647
acceptance_criteria: [AC-R8]  # the registry and codegen rules the docs teach
risk_zone: red
status: done
branch: s38-p10-t55
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T55
---

## Objective
validate_docs is green and a fresh session can register a tool and a run-step kind from the docs
alone.

## Built
- `docs/specs/SPEC-647-p10-agent-runtime-v2.md`: §5 "As built" (each §3 area, its files, what is
  open); the C6 path corrected to `docs/contracts/agent-runs.md`.
- `docs/architecture/reference/ai-agent.md`: "Runtime v2": the v2 spec, register a tool (seven
  steps), register a run-step kind, proposals and approved writes, real time; "Not yet" updated.
- `docs/architecture/ai-threat-model.md`: "Tool use under runtime v2", TU-01 to TU-09 with the
  tests that cover each; a checklist line; a review row.
- READMEs: `agents` (runtime v2 map), `workbench` (how a session works), `notifications` (`GET
  /v1/events`: topics, invalidations, delivery, off switch).
- Skills: `.claude/skills/ai-agent` (runtime v2 order of work), `.claude/skills/temporal-workflow`
  (agent runs and sessions).
- `docs/contracts/p10-consumer-notes.md`: P-09, T-04, W-02, I-02, K-03, K-04, A-07.
- `backend/tests/unit/agents/test_p10t55_docs_resolve.py`: every API, keyword, field, file and
  command the recipe names resolves on the tree (14 pass).

## validate_docs
Green for this task's files. The tree has 26 violations from earlier S38 task files and SPEC-652
(AC ids not in their SPECs; SPEC-652's frontmatter): fixed in the end-pass round on their branches.

## Progress log
- 2026-11-12: built; docs test passes.
