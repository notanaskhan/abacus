---
id: TASK-8938
title: "F-08-T25: Independent AC tests for presence anchors"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-f08t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: F-08-T25
---

## Objective
Independent AC tests for presence anchors (ADR-078). Acceptance: Tests prove unregistered kinds and unreadable objects are refused, heartbeats vanish after 45 s, and the SSE topic carries identifiers only.

## Done
- backend/tests/integration/backfill/test_f08t25_presence_ac.py from F-08 §3 F1 and docs/contracts/presence.md (6 tests): unregistered kind 404; unreadable object (other firm, off-team) 404; heartbeat shows to others, never the viewer; gone after 45 s (row aged through the seeder); identifiers only, not audited, no outbox row; client principal refused

## Progress log
- `2026-11-23` — 2026-11-23: written from the epic and contract only; lint and pyright clean. Integration run (Docker) in the end pass.
