---
id: TASK-2504
title: A-03-T05 migration 0520 sampling (populations, ties, sample sets, frozen versions, strata, items)
spec: SPEC-580
acceptance_criteria: [AC-13, AC-14, AC-15]
risk_zone: amber
status: done
epic: A-03
plan_key: A-03-T05
branch: s20-a03-t05
created: 2026-10-30
updated: 2026-10-30
---

## Objective
The sampling engine's tables, expand-only, with the database guarding what ADR-340 decides:
frozen versions, human-only approval, one approved version per set, overrides with a rationale.

## Plan (amber)
- `backend/migrations/versions/0520_sampling.py` (revises 0406; renumber/re-chain at merge if S18's
  0460–0466 land first): `sample_populations`, `sample_population_records`, `completeness_ties`,
  `sample_sets`, `sample_set_versions`, `sample_strata`, `sample_items`; forced RLS; column-level
  insert grants; update grants only on `sample_sets` (title, purpose, step) and
  `sample_set_versions` (status, hashes, failure code, approval stamps, superseded_by).
- Guards: `sample_set_versions_guard` (insert as drawing, numbered in order; drawing → draft |
  failed with the outcome columns only; draft → approved | superseded with the decision columns
  only; approved → superseded; everything else and every DELETE/TRUNCATE `version_frozen`;
  approval only in a person's session `approver_not_human`); `sample_rows_while_drawing` (strata,
  items); `sample_population_records_with_population` (records with their population's
  transaction, the 0051 pattern). CHECKs: `approved_actor_kind = 'human'`, approval stamps,
  override rationale and below the computed size, `final_size = coalesce(override, computed)`,
  exactly one source per population, tie/off coherence.
- `threshold_policies.kind` += `attribute_sample_sizes` (constraint swap in the same file).
- `sampling/registry.py`: TABLES, INSERT_ONLY, INSERT_COLUMNS, UPDATE_COLUMNS;
  `tests/security/test_tenant_isolation.py` lists the seven tables; glossary table names.
- **Name (DEC-1554):** fieldwork already owns `populations` (0057, journal-entry testing,
  ADR-132), so the plan's `populations`/`population_records` are `sample_populations`/
  `sample_population_records`.
- Rollback: downgrade drops the seven tables and functions and restores the kind CHECK.

## Acceptance
| Check | Test |
|---|---|
| up/down/up, schema_check, forced RLS | `tests/integration/backfill/test_a03t05_sampling_tables.py::test_ac13_*`; tenant isolation suite |
| Frozen version, permitted moves only | `test_ac14_a_draft_refuses_any_change_but_its_status_moves` |
| Non-human approval refused by the DB | `test_ac14_a_non_human_approval_is_refused_by_the_database` |
| Numbering, one approved, no delete | `test_ac14_versions_number_in_order_*` |
| Override rules | `test_ac14_an_override_needs_a_rationale_and_a_smaller_size` |
| Items/strata while drawing; records with population | `test_ac14_items_and_strata_*` |
| Size-table kind | `test_ac15_threshold_policies_accept_attribute_sample_sizes` |

## Progress log
- 2026-10-30: built (tests first, run at the end review). DEC-1554.
