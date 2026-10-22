---
id: TASK-412
title: Review package scaffolding - fail-closed slots for decision kinds, gates, field owners, fix runners, suggestion targets and proposal adapters (P-04-T06)
spec: SPEC-308
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-04
plan_key: P-04-T06
branch: p04-t06-review-slots
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"An unregistered target, decision kind, gate kind or field owner is refused or answers 503 in tests, and import-linter rejects any review import of a service-line module."

## What changed
- **`review.api`:**
  - `register_decision_kind(DecisionKind(code, reserved_role, options))`: reserved roles are engagement partner, manager, EQR reviewer or signer, and options are computed by code (ADR-050);
  - `register_gate_kind`;
  - `register_field_owner(FieldOwner(target_type, value_of, tri_fields))`, which records which fields hold TRI so C19 can gate them;
  - `register_fix_runner`;
  - `register_reviewable`, which already existed.
  - Lookups fail closed. An unregistered kind answers 422 `unregistered_kind`, a gate whose owner raises is unmet, and a missing fix runner answers 503.
- **`agents.api`:**
  - `register_suggestion_target`: a suggestion on an unregistered target answers 422 `unregistered_target`;
  - `register_proposal_adapter`: approving a proposal whose adapter is missing answers 503.
  - Agents never write another module's rows.
- **Import boundary:** `MODULE_DEPENDENCIES["review"]` in `banned_patterns` (BOUND-001) already allows only the base modules plus `engagements`. Importing a service-line module from `review` already fails the gate, so nothing changed.
- **Not done:** the Pydantic models with classification tags arrive with the C3 stubs (P-04-T07 and T08), where the routes need them.

## Progress log
- 2026-10-22: the new `tests/unit/review/test_review_slots.py` (4 tests) passes. ruff, pyright and banned_patterns are clean.
