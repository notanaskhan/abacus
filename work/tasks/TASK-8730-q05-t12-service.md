---
id: TASK-8730
title: "Q-05-T12: Post-issuance case service, code comparison, EP decision and routes"
spec: SPEC-711
acceptance_criteria: [AC-15, AC-16, AC-17, AC-18]
risk_zone: red
status: in-review
branch: s51p-q05-t12-service
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: Q-05-T12
---

## Objective
Finish Q-05-T12 (TASK-8718): assurance/post_issuance.py (red, ARCHIVE-001 allowlisted) opens cases on an archived audit under the post_issuance kind, compares the corrected figures with A-05's certified trust-report lines and evaluates the difference against the materiality in force at release (code), and records the EP's decision on the case row; AUD-30 routes live behind audit.post_issuance.

## Plan (red)
1. Migration 0986: type reissuance_request; source_evidence_version_id; decision, decided_by, decided_at, rationale_sealed, decided_actor_kind (human-only CHECK) with a whole-decision CHECK; grants; registry columns.
2. Matrix: post_issuance.decide (EP, fresh MFA, independence, archived_exempt post_issuance, agent deny); permission_matrix regenerated.
3. post_issuance.py: cases/case (post_issuance.read on the work item), open_case (409 not_archived; PI-nn under an advisory lock; sealed description; PostIssuanceCaseOpened to the EPs), compare_case (only matching certified lines; 409 comparison_unavailable; insert-only), require_comparison, decide (code options; rationale; 409 post_issuance_case_decided).
4. post_issuance_contract.py: list, detail, create, comparison, decision live; analysis 409 until compared and 501 after (the prompt follows its eval suite, ADR-079); reissue 501 (A-07's reissue path is not built).
5. docs/contracts/audit-completion.md rows; make generate; tests/integration/backfill/test_q05t12_post_issuance_cases.py.

## Progress log
- `2026-11-19` — Built. Decision on the case row, not a P-04 card: the locked audit's decision_cards and decisions are behind archived_guard() and widening the guard would contradict ADR P-43; the case row is the table the post_issuance kind reaches (DEC-5724). Not built (blocked on other epics): the agent's analysis run (its prompt follows Q-05-T10's suite), the reissue through A-07's reissue path (not on main), the inbox destination post_issuance_source (N-01 slot) and the AUD-30 seed. The comparison happy path is covered by the compute unit tests; the DB test covers the guard path. Gates and tests run once at the S51 end pass (build first, test last).
