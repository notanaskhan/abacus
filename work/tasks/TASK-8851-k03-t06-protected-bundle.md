---
id: TASK-8851
title: "K-03-T06: K-03 protected bundle"
spec: SPEC-720
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-k03t06
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: K-03-T06
---

## Objective
The bundle merges first in the Thu Oct 26, 2028 train with both founders' approval, make generate is clean, and the generated allow/deny tests deny every new write action to agent.

## Done
- matrix rows (methodology, engagements, workpapers) + codegen
- three flags + _flags.py
- activity catalogue labels
- notification kind template_update_available
- glossary rows
- DEC-5848

## Progress log
- `2026-11-20` — Plan (red): registry-only; rollback = revert. make generate and generated allow/deny tests at the end pass.
