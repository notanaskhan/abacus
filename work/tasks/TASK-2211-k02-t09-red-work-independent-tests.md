---
id: TASK-2211
title: K-02-T09 independent AC tests for K-02's red work
spec: SPEC-500
acceptance_criteria: [AC-1, AC-2, AC-8, AC-9, AC-10]
risk_zone: red
status: in-review
epic: K-02
plan_key: K-02-T09
branch: s17-k02-t09
created: 2026-10-30
updated: 2026-10-30
---

## Objective
ADR-078 independent acceptance tests for N's red work (K-02-T01 matrix rows and the
`owner_of_target` condition; K-02-T03 migration 0400), written by AY from K-02 §4.2, §4.4, §6,
ADR-300 and `docs/contracts/rules-tables.md`, not from the implementing suites:
`owner_of_target` truth table, agent and portal deny on every K-02 write, global-table
privileges, owner-only definer functions not executable by the app, the approver-differs-from-
drafter CHECK, immutability after publish.

Acceptance (backlog row): "The tests fail if any K-02 write allows the agent principal or if
abacus_app can read a draft reference-set version."

## Plan (red)
- `backend/tests/unit/identity/test_k02t09_k02_matrix_independent.py`: the matrix decisions for
  every K-02 write and read; `conditions_hold` truth table for `owner_of_target`; no other action
  carries it; no reference-set or due-date write action or route; an agent run with every K-02
  write in its scope (initiated by a practice leader or quality partner, even named as owner)
  refused by `authorise`.
- `backend/tests/integration/backfill/test_k02t09_reference_sets_independent.py`: every
  privilege of every application role on the three tables read from the catalog; EXECUTE on the
  readers (the app only) and the operators' functions (no application role, not PUBLIC); a draft
  absent from all three readers; the two-person CHECK when the status is written directly; a
  published version frozen (payload, date, handles, hash, back to draft, delete), withdrawal
  two-person and final; the publication log insert-only.
- `banned_patterns.py`: DB-001 exclusion for the catalog suite (it connects as the owner and the
  app, like K-02-T03's).
- No product code, no migration. Rollback: revert.

## Acceptance
| Check | Test |
|---|---|
| Any K-02 write allowing the agent fails the suite | `test_every_k02_write_denies_*`, `test_an_agent_run_is_refused_*` |
| owner_of_target truth table | `test_owner_of_target_truth_table` |
| abacus_app reading a draft fails the suite | `test_the_app_never_reads_a_draft_through_any_reader`, `test_no_application_role_holds_any_privilege_on_the_tables` |
| Owner-only functions | `test_the_app_executes_the_readers_and_no_operator_function` |
| Two-person CHECK, immutability | `test_the_database_refuses_*`, `test_a_published_version_is_frozen_*`, `test_the_publication_log_is_insert_only` |

## Progress log
- 2026-10-30: written in S17 Lane 2 (AY); run in the end review.
