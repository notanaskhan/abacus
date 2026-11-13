---
id: TASK-7917
title: I-02-T19 Independent AC and security tests for I-02-T04, T06, T07, T08, T11, T13
plan_key: I-02-T19
spec: SPEC-654
acceptance_criteria: [AC-3.11]  # consent and citation mutations fail; no audit row carries brief content
risk_zone: red
status: in-review
branch: i02-t19-independent
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
ADR-078 and security suite: forced RLS and terminal immutability of `daily_briefings`, agent deny
on briefing actions, consent refused before any model call, why lines need citations or facts,
untrusted client strings, idempotent dispatch, no brief content in audit rows or events.

## Plan
- Test: `backend/tests/unit/agents/test_i02t19_independent.py`.

## Partial
- Solo edition. Replay histories and live-database RLS stay in the integration and workflow
  suites; here the guards are asserted on the services and migrations themselves.

## Progress log
- 2026-11-13: written, not run (S42 end pass).
