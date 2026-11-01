---
id: TASK-2912
title: A-05-T15 migration 0642 ebp_participants_testing
spec: SPEC-640
acceptance_criteria: [AC-13]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T15
branch: s24-a05-t15 (stacked on s24-a05-t09)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

A-05 M2: the census (`ebp_source_imports`, `ebp_participants`), the shared attribute grid (`attribute_tests`, insert-only `test_attribute_results`) and `ebp_population_queries`.

## Acceptance (backlog)

No plaintext SSN or DOB column exists, result rows are insert-only, and a human-only CHECK refuses an agent writing pass, exception or no_effect.

## Plan

- Migration `0642_ebp_participants_testing` (expand-only, on 0641): five tables, work-item scoped, forced RLS, no DELETE for the app role; SSN and DOB sealed with HMAC fingerprints (SSN last four), no plaintext column; results and queries insert-only; a result's `pass`, `exception`, `no_effect` need `actor_kind = 'human'` and every result is the transaction's own actor's; an import is a person's; participants never updated; column grants listed in `INSERTS` and `UPDATES`.
- Registries: `assurance/registry.py` (`EBP_PARTICIPANT_TABLES`, insert-only queries, insert and update columns), `workpapers/registry.py` (attribute tests and results).
- Test: `tests/integration/test_a05t15_ebp_participants_migration.py`.
- The services (import, sealing with the fingerprint key, the grid) are A-05-T16 and later; the fingerprint pepper is a human to-do (vault secret) before any import runs.

## Progress log

- 2026-11-01: built in abacus-s24, stacked on A-05-T09 (0641). Tests written, not run.
