---
id: TASK-8537
title: "C-01-T49: close.agent never-verbs at the tool, route and database layers"
spec: SPEC-655
acceptance_criteria: [AC-50]
risk_zone: red
status: in-review
branch: c01-t47-t49-independent
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T49
---

## Objective
ADR-078 independent tests: the close agent never resolves, approves, signs, publishes, adopts, incorporates or sends (I-AGENT-NEVER), proven at the tool, route and database layers.

## Plan (red)
1. tests/unit/closes/test_c01t49_agent_never.py: no close tool named for a never-verb; the one write is a suggestion; every closes/review matrix action with a never-verb denies agent and system; 0885's human-only CHECKs on resolutions and acceptances

## Progress log
- `2026-11-17` — Built; 15 pass. Scope pinning and untrusted wrapping are covered by the C17 runtime suites (P-10) the end pass runs. Gates and tests run once at the S49 end pass (build first, test last).
