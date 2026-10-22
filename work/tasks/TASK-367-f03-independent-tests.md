---
id: TASK-367
title: Independent AC tests (ADR-078) for work items, lifecycle, gate policy and slots (F-03-T20)
spec: SPEC-025
acceptance_criteria: [AC-7]
risk_zone: green
status: done
epic: F-03
plan_key: F-03-T20
branch: f03-t20-independent
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Tests … cover every row of the chapter 03 3.1.3 lifecycle and gate-policy tables and pass on
main." Written from chapter 03 §3.1.3, §3.1.4 and §2.4 and F-03 stories 1.1 to 1.3.

## Scope
- `backend/tests/acceptance/test_f03_lifecycle.py` (35 cases): every lifecycle row as a legal move
  with its actor; the human rows' matrix (the roles named allow, agents and the system deny, fresh
  MFA); the table is the whole lifecycle; illegal moves are 409; INV-1 (agent, system and support
  principals refused before any write); INV-5 (one audit event and one status-changed event per
  move); every gate-policy row; firm overrides only tighten; fail-closed slots.
- `backend/tests/integration/test_f03_lifecycle_migrations.py`: engagements seeded at 0067, then
  head: each has one assurance work item and one primary entity link, the archived one's work item
  is archived, every row scoped; down to 0067 and up again with a clean schema check.

## Findings
None: every row held.
