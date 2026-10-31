---
id: TASK-2515
title: P-11-T13 Brightwater Hale template content through the import API, plus the pilot template-import guide
spec: SPEC-520  # AC-1 to AC-5 (the import and publication it exercises); C11 v1
acceptance_criteria: [AC-1, AC-3]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T13
branch: s20b-p11-t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Brightwater Hale template content loaded through the scenario loader's service APIs (CAS, audit
and tax engagement letters, separate Sec. 7216 consent documents, rep letter, AU-C 260 planning
letter, report shells, notice response, delivery cover letter) in synthetic wording, plus a pilot
template-import guide.

Acceptance (backlog row): "make seed-demo publishes every template through the import API into
the synthetic tenant only, and a scan finds no template text in any migration or constant."

## Plan (amber)
- Slice `report_templates` (`abacus_tools/.../brightwater_hale/report_templates.py`): twelve
  bundles; events `reporting.template_imported` (GH) and `reporting.template_published` (MO);
  the `reporting.generated_documents` flag on. Loader handlers call
  `reporting.api.import_template_bundle` and `publish_template` (new re-exports of the routes'
  services). Opt-in: `make seed-demo SLICE=report_templates`.
- Guide `docs/operations/template-import.md`.
- **Bugs found on main:** `SELECT … FOR UPDATE` on `report_templates` needed an UPDATE grant the
  app role lacks, and the import's audit reference carried a string. Main fixed both while this
  row was in review; the rebase keeps main's fix and this row changes nothing in methodology.
- Tests: `tests/integration/test_p11t13_template_content.py`.
- Rollback: drop the slice from the loader table; the lock change is behaviour-preserving.

## Decisions
DEC-1563.

## Progress log
- `2026-10-31` — Built on `s20b-p11-t13` off main 7d4def8e5; rebased onto main 6ece192f6 at the end review. test_p11t13 (15), unit reporting,
  C11 contracts, P-11-T06 schema: 175 passed.
