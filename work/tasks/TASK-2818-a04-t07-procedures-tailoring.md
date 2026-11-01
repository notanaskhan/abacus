---
id: TASK-2818
title: A-04-T07 procedures, program tailoring, pack validation and the service-organization inventory
spec: SPEC-620
acceptance_criteria: [AC-9, AC-23]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T07
branch: s23-a04-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective

A-04 §3.1 AC1.9, §6 AC6.1, §7 AC7.1. Instantiate an audit work item's procedures from the pinned methodology version and let a manager or the engagement partner tailor the non-mandatory ones. Validate the pack by code before any draft runs. Serve the service-organization inventory that AUD-04 and AUD-10 share.

## Acceptance (backlog)

Northwind gets 67 procedures with 21 mandatory, tailoring a mandatory step returns 409 mandatory_step, and validating EBP v3 returns the BH-EBP-140 step 8 error verbatim.

## Plan

- **Migration `0614_procedure_tailoring`** (expand-only, on 0613).
  - `program_procedures.row_version`: a tailoring names the version it saw. GRANT INSERT on `linked_work` and UPDATE on `row_version`.
  - `program_steps.template_refs text[]`: at most 20 entries, each `request:<key>` or `workpaper:<kind>`. GRANT INSERT and UPDATE.
- **Methodology.** The workbook gets an optional `templates` column (`invalid_template_ref`). The import and draft copies carry it. Two new pieces:
  - `version_steps(tenant, version_id)`, labelled "EBP v3".
  - The template-library slot `register_template_library` / `templates_held` (OQ-15).
- **Workpapers `procedures.py`.**
  - `procedures_of` writes the procedures once, as the system context, audited `procedure.instantiated`.
  - `tailor`: 409 `mandatory_step`, 409 `version_conflict`, 422 `rationale_required`; audited `procedure.tailored` on target `program_procedure`.
  - `pack_errors` / `validate_pack`: `pack_configuration_error`, with the AUD-09 d text as the exception's message and identifiers as facts.
  - Workpapers registers its own kinds as a library.
- **Assurance `service_orgs.py`.**
  - List, row, add (409 `duplicate_name`) and edit against `expected_version`.
  - Audited `service_org.created` and `service_org.edited`.
  - Audit owner `service_organization`.
- **Routes.** `program-tailoring`, `procedures/{id}` PATCH and the four `/service-organizations*` routes go live. Their 501 is dropped and they move to the stub test's SERVED set, following DEC-1762.
- **Seed.** Brightwater Hale EBP v3 plants `request:soc1_bridge_letter` on BH-EBP-140 step 8. No K-03 library holds it yet.
- **Contracts.** `workpapers-core.md` and `audit-planning.md`: status, behaviour, errors, audit names.
- **Tests:** `tests/integration/backfill/test_a04t07_procedures.py`. The stub tests are updated. Schema-check update columns.
- **Rollback.** `downgrade()` drops both columns and their grants. The routes return to their earlier behaviour by reverting the module code.

## Decisions made during this task

DEC-1867.

## Progress log

- `2026-11-01`: built migration 0614, services, routes, seed defect, contracts and tests.
  - The row's own test passed 6/6 before the build-first rule was restated.
  - The remaining suites run in the end pass.
  - Mistakes made twice here:
    - Free text in DomainError facts.
    - A bool Ref in an audit event.
  - These are candidates for a lint rule.
