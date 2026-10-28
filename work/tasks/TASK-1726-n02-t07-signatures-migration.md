---
id: TASK-1726
title: N-02-T07 Signatures v1 migration (C7 tables)
spec: N-02 §4.2
acceptance_criteria: [N-02-T07]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T07
branch: s14-n02-t07
created: 2026-10-28
updated: 2026-10-28
---

## Objective
C7's twelve tables in one reversible migration (0292) with forced RLS, insert-only evidence and
human-only actor columns. Acceptance (backlog row): "The migration applies and reverses on a
seeded database, insert-only triggers refuse UPDATE and DELETE, and the single-head check stays
green."

## Plan (red)
- Migration `0292_signatures_v1` (down `0291`): `envelopes`, `envelope_numbers`,
  `envelope_documents`, `envelope_signers`, `envelope_fields`, insert-only `envelope_events`,
  `envelope_provider_calls`, `signature_evidence`, `esign_disclosures`, `esign_acceptances`;
  `envelope_policies`, `signing_sessions`. Status CHECKs carry the registry's `envelope` and
  `envelope_signer` stored codes. Classification in the migration docstring (ADR-031).
- Trigger `envelopes_human_actor`: actor columns set only by the named person; number, client,
  provider fixed; final status fixed (DEC-816). Trigger `signatures_rows_immutable` on the five
  insert-only tables.
- `signatures/registry.py` (tables, insert-only, column grants), `schema_check.IMMUTABLE_TABLES`,
  the schema-check pin, the generated tenant-isolation list (`make regenerate`).
- No routes, flags or matrix rows (T08 adds them). No data inserted.
- Rollback: downgrade 0292 (drops the twelve tables and two functions).

## Acceptance
| Check | Test |
|---|---|
| Applies and reverses on a seeded database | `backend/tests/integration/test_n02t07_signatures_schema.py::test_ac_the_migration_applies_and_reverses_on_a_seeded_database` |
| Insert-only triggers refuse UPDATE and DELETE | `…::test_ac_insert_only_tables_refuse_update_delete_and_truncate`, `…::test_ac_an_envelope_event_once_written_is_never_changed` |
| Single head | `…::test_ac_the_single_head_check_stays_green` |
| RLS, human actors, final status, e-file policy, KBA cap, 5-minute sessions | seven tests |

## Progress log
- `2026-10-28` — Built. ruff and pyright clean. Tests written, not run yet (run in the end-of-batch
  review, per Ayush's instruction for this run).

## Handoff
- **Current state:** PR open, held for the batch.
- **Next:** N-01-T07 (0293), then N-02-T08 on this branch.
