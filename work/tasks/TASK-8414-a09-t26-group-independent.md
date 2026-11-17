---
id: TASK-8414
title: "A-09-T26: Independent AC tests for N's consolidation, elimination and coverage work"
spec: SPEC-658
acceptance_criteria: [AC-2, AC-3, AC-4]
risk_zone: red
status: in-review
branch: a09-t26-group-independent
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T26
---

## Objective
Spec section: docs/plan/epics/A-09.md §6, §8 (ADR-078). Independent AC tests: RLS, structure freeze, human-only finalize and missing-TB refusal, posting CHECK and target, agent and system refusal on approve and post, lock blocks edits, reopen needs a reason, coverage uniqueness and backfill, pull-all reauth path, no write capability.

## Plan (red)
1. `backend/tests/security/test_a09t26_group_independent.py` from SPEC-658 and A-09 §6, against the database: RLS hides another firm's consolidation; finalize and lock refused for agent and system actors; lock before finalize refused; an entry decision under an agent or system actor refused (no agent-approved elimination); a second live ledger coverage row for a covered subsidiary refused; no registered write tool for consolidation, elimination, posting or coverage; `_refused` with a planted-allow test so a build missing a rule fails.

## Progress log
- `2026-11-17` — Written in the S48 sequential stack; ruff clean; not run (end pass). Partial: the service-level properties (structure freeze, lock blocks edits, reopen reason, missing-TB refusal, the pull-all reauth path) are covered by A-09-T19/T18's own tests and not yet restated here independently; posting-target CHECK not restated. Gates and tests run once at the S48 end pass (build first, test last).
