---
id: TASK-1500
title: The firm export carries one A-01 engagement export package per engagement (Q-02-T47)
spec: SPEC-341
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: Q-02
plan_key: Q-02-T47
branch: s12b-q02-t47
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Replace the firm export's empty `packages` (DEC-508's v1 skeleton) with one A-01 engagement export
package per engagement, plus a firm index and a manifest that verifies against the archive.
Acceptance: a canary firm export contains one verified package per engagement and its manifest
hashes match the archive.

## Plan
- `evidence/firm_export_packages.py` (new): for every engagement of the firm
  (`engagements.api.all_engagement_ids`, archived included), as the approver
  (`export_sections.acting_person`): `evidence.read` on the engagement (else `not_readable`), its
  assurance work item (else `not_an_audit`), its asked PBC binders, then A-01's planner, section
  providers and builder into a scratch file. An unsafe plan is `unsafe_contents`; an integrity
  mismatch fails the export (RB-29).
- `evidence/firm_export_activities.py`: one audit sequence for the export; `write_archive` stores
  each package at `packages/<engagement_id>.zip` (stored, chunked) and lists it in `index.json`
  (format 0.2, `packages`, `omitted`) and `manifest.json` (its stored bytes' digest). The package
  activity turns an integrity mismatch into a non-retryable error.
- `export_activities.evidence_files`: public name for the existing file reader.
- Docs: compliance-kernel §3; DEC-640.
- Tests: `tests/integration/test_q02t47_firm_export_packages.py` (the canary export verifies, every
  engagement accounted for once; a firm with no engagements still verifies). The Q-02-T43 archive
  test keeps passing (its firm has no engagements).
- Rollback: revert the commit; the archive returns to the 0.1 skeleton. No migration.

## Progress log
- 2026-10-27: built; tests written, not yet run (the S12 batch runs one test pass at the end, at
  Ayush's direction). DEC-640.
