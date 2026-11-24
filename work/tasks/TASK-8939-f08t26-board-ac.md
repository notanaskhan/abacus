---
id: TASK-8939
title: "F-08-T26: Independent AC tests for the Board kit"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-f08t26
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: F-08-T26
---

## Objective
Independent AC tests for the Board kit (ADR-078). Acceptance: Tests prove no drop path invokes a sign-off, approve, release or send intent (INV-1), guarded drops route to onOpenSignOff, and a disabled toggle cannot dispatch.

## Done
- packages/ui/src/board/board.ac.test.tsx from F-08 §3 B1/B2 (5 tests): a move emits only onMoveIntent (no final-verb control); guarded result offers Open sign-off… which alone calls onOpenSignOff; disabled or off toggle never sends runAgent:true; allowed-and-on asks for a run and nothing more

## Progress log
- `2026-11-23` — 2026-11-23: written from the epic; the Move to… menu stands in for a pointer drag in jsdom (B1 says it carries the same intent). 5 pass.
