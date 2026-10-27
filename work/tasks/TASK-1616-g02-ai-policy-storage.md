---
id: TASK-1616
title: AI policy drafts and versions, compiled defaults, gate catalogue, validator (G-02-T23)
spec: SPEC-349
acceptance_criteria: [AC-31, AC-32, AC-37, AC-38]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T23
branch: s13-g02-t23
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Store the AI policy safely: drafts, insert-only versions with two-person and human-only rules, compiled platform defaults with a stricter-only validator, the twelve-gate catalogue checked against the matrix, and every firm's carried-over v1.

## Plan
- Migration 0272 (down 0271); agents registry.
- `docs/architecture/ai-policy-defaults.yaml` (protected) → `abacus_tools/codegen/ai_policy_defaults.py` → `agents/_ai_policy_defaults.py`; added to `GENERATORS`.
- `agents/ai_policy_validator.py`; `agents/ai_policy_store.py` (effective sections, the level provider); identity `register_autonomy_level_provider`.
- Tests: `tests/unit/agents/test_g02t23_ai_policy_defaults.py`, `tests/integration/test_g02t23_autonomy_policy_migration.py`.
- DEC-711. Rollback: downgrade 0272; unregistering the provider restores the firm setting.

## Progress log
- 2026-10-28: built. Also fixed N-01-T06's 0270 backfill (FORCE RLS lifted for the statement), committed separately on this branch.
