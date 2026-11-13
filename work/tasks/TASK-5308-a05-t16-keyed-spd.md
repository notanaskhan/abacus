---
id: TASK-5308
title: A-05-T16 keyed SPD and amendment values make EBP-02's conflict and amendment tag live
spec: SPEC-640
acceptance_criteria: [AC-14]  # F2: SPD conflicts and amendment tags on the review
risk_zone: amber
status: done
epic: A-05
plan_key: A-05-T16
branch: s25d-a05-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s25d
created: 2026-11-08
updated: 2026-11-08
---

## Objective
DV-EBP-02-6: c's SPD conflict and d's amendment tag were null from the live service, because nothing
let a person enter the SPD's wording. Build the keyed path (DV-EBP-02-1) and compute both from it.

## Plan (amber)
- Matrix `ebp_provision.enter`; route `PUT /ebp/provisions/{key}/documents/{source}`; contract
  `ProvisionDocumentIn`, `ConflictSourceOut.page` and `match_id`; `make regenerate`, `make generate`.
- `ebp_provisions.record_document_value`: human only, a verified C4 quote in the same unit of work,
  upsert on 0610's `ebp_provisions`; audit `ebp_provision.document_value_recorded`.
- `workpapers.api.latest_version_id`.
- `review_of` reads the values; `compared` gives the conflict, its source and the amendment tag.
- No migration (0610's table). Rollback: revert; rows stay inert.

## Tests
`tests/integration/trust_kit/test_a05t16_spd_values.py` (a real word layer: verified and refused
quotes), `tests/unit/assurance/test_a05t16_plan_reads.py` (comparison, amendment tag).

## Progress log
- 2026-11-08: built. No screen keys the values: no artboard shows the entry, so the route is the path.

## Decisions made during this task
DEC-2489.
