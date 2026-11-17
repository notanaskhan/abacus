---
id: TASK-8511
title: "T-06-T03: S49 T-06 protected bundle: matrix and conditions, flags and renewals, error codes, kinds, HANDOFF-001"
spec: SPEC-702
acceptance_criteria: [AC-29, AC-33, AC-34, AC-35]
risk_zone: red
status: in-review
branch: t06-t03-protected-bundle
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: T-06-T03
---

## Objective
Spec section: docs/plan/epics/T-06.md §4.3, §4.7–§4.9. Matrix rows in tax, organisations and ledger with conditions tb_handoff_source_released, same_client and decision_owner_contact; six flags; registry-only renewal of T-04's and T-05's flags; error codes; notification kinds; protected paths and HANDOFF-001.

## Plan (red)
1. identity authz: three resource conditions (matrix CONDITION_KEYS and flag conditions, Rule fields, ConditionFacts, conditions_hold), fail closed while their facts are unknown.
2. Matrix: tax 15 actions (reads at agent task_scope with consent use+ai_disclosure; approve, send, download, writes human-only; decision.send_to_client needs decision_owner_contact), organisations relationship.create/update/end + graph_layout.save (OQ-6), ledger tb_handoff.preview/create/read (create needs tb_handoff_source_released and same_client). Fresh MFA: form_preview.download_draft (export).
3. Flags: tax.entity_depth, tax.other_entity_workpapers, tax.form_preview, tax.tb_handoff, clients.relationship_map, agents.tax_entity_modes; T-04/T-05's six renewed registry-only to 2027-05-16.
4. Error codes: tax/entity_depth_errors.py, ledger/handoff_errors.py, organisations/relationship_errors.py (422s).
5. Notification kinds decision_answered (event tax_decision.answered: decision.decided is the review grammar's), tb_handoff_received, tb_handoff_superseded.
6. HANDOFF-001; protected-paths names tax/compute/parameters/ and ledger/tb_handoff.py.
7. Fix found here: C-02-T05's write_operations collided with tax's (0561); the W1 tables are ledger_write_operations and ledger_write_evidence.
8. Rollback: revert; flags default off, conditions fail closed.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5511). Matrix, flags and error codes regenerate cleanly; banned_patterns and seed_contamination clean. Gate, decision and reviewable-section kinds register with their services (T-06-T20, T35), like C-02's T14; TABLE_OWNERS arrive with T-06-T10/T11/T12. Gates and tests run once at the S49 end pass (build first, test last).
