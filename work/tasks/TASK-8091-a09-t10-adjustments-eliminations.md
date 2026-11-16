---
id: TASK-8091
title: "A-09-T10: Migration 0896_adjustments_eliminations"
spec: SPEC-658
acceptance_criteria: [AUD-33]
risk_zone: red
status: in-review
branch: a09-t10-adjustments-eliminations
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: A-09-T10
---

## Plan (red, expand-only)
- `proposed_entries`: + `consolidation_id` (FK consolidations), `posting_target`
  (`consolidation_layer` only), `display_code` (`E1a`); a posting target needs kind elimination
  and a consolidation; a consolidation only on an elimination.
- Replace `pe_posting_dormant`: posted/failed_post/reversed only for an elimination whose target
  is the consolidation layer (Accrued's own layer, never a client system: ADR-040 stands).
- `proposed_entry_lines`: + `client_entity_id` (FK client_entities), `consolidation_level` (1-3,
  needs an entity); deferred constraint trigger `proposed_entry_line_entity` refuses at commit a
  line whose entity is not one of its entry's consolidation entities.
- Grants: insert on the new columns; update on the line columns (while open: the lock trigger).
- Rollback: `alembic downgrade 0895` restores the strict constraint (no posted elimination may
  exist then: the service lands in A-09-T20).

## Built
As planned. Tests: `tests/integration/test_a09_s46_migrations.py` (with T11 and T12; end pass).

## Progress log
- `2026-11-15` — Built.
