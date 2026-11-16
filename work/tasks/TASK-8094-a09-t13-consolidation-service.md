---
id: TASK-8094
title: "A-09-T13: Consolidation service in ledger, routes in assurance"
spec: SPEC-658
acceptance_criteria: [AC-1, AC-2]
risk_zone: red
status: in-review
branch: a09-t13-consolidation-service
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: A-09-T13
---

## Plan (red)
- `ledger/consolidation.py` (pure ledger): create, facts, edit and structure with the row version
  (If-Match), discard (status), TB attach (upload snapshot, evidence's snapshot, or the entity's
  newest for a covering connection), not-needed, human-only finalize refusing missing slots.
- Migration `0899_consolidation_tb_supersede`: the `superseded_by` FK DEFERRABLE INITIALLY
  DEFERRED, so a slot can be replaced in one transaction.
- `connections/coverage.py`: `covers`, `cover_entities` (a consolidation's source connection
  covers its structure's entities; a taken entity is 409 `entity_already_covered`).
- `assurance/group_consolidation.py` + routes in `group_contract.py`; the gate now requires the
  `group_audit` capability (entitlement and both rollout flags, A-09-T09).
- Rollback: revert; `alembic downgrade 0898`.

## Built
As planned. Finalize adopts one TB of record per entity in the same transaction; each adoption
emits `TrialBalanceVersionCreated`, whose subscriber starts that entity's mapping run (five runs
for Harlow & Pike). Missing slots are derived (required minus stored), with stable uuid5 ids so
"Mark not needed" can name one. Audit owner `consolidation` registered; actions reviewed.
Tests: `tests/unit/ledger/test_a09t13_consolidation_rules.py` (10 pass);
`tests/integration/test_a09t13_consolidation.py` (end pass).

## Partial
- Structure proposal (P-35 suggestion), lock, reopen and the consolidated TB stay 501 for their
  own rows (A-09-T14 FE, T18, T19).
- `upload_id` names the ledger snapshot an upload produced (the import route makes it); a direct
  multipart attach joins A-09-T18's bulk upload.

## Progress log
- `2026-11-15` — Built (DEC-5070).
