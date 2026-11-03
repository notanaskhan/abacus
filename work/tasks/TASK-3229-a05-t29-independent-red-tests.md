---
id: TASK-3229
title: A-05-T29 Independent AC tests for A-05's red work
spec: SPEC-640
acceptance_criteria: [AC-13, AC-16]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T29
branch: s26-a05-t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3229 · A-05-T29 · Independent AC tests for A-05's red work (T12, T13, T15, T18, T21)

**Epic:** A-05 · **Sprint:** S26 · **Type:** TEST · **Zone:** amber · **Depends on:** A-05-T12, T13, T15, T18, T21 · **Status:** in-review

## Built
`backend/tests/contracts/a05_ebp/test_a05t29_independent.py` (ADR-078): the section drafter has no tools; the EBP modes are on the one spec; no EBP prompt carries an SSN or asks for an SSN or birth date (only forbids or masks them); 0642's five tables are tenant-scoped with DELETE and TRUNCATE revoked and results and population queries insert-only; `attribute_result.marked` is human-only; `pii.reveal` denies agent, system and client principals and requires onshore and fresh MFA; every EBP write denies the system principal.

## Partial
- "No SSN or DOB pattern in logs, audit rows, outbox payloads or model context" is held here at the prompt and declaration level; the runtime scan of log, audit and outbox sinks is RB-42's seeded audit and T18's integration suite.

## Progress log
- 2026-11-03: written; ruff and pyright clean; not run (end pass).
