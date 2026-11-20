---
id: TASK-8814
title: "C-02-T28: PackageAssemblyWorkflow and render"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-c02t28
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: C-02-T28
---

## Objective
Two renders of the same posted TB are byte-identical, every page carries 'No assurance is provided.' for August and none does for the illustrative December package.

## Done
- closes/package_render.py: generate (DET run close.package_assembler, a new deliverable version keeping commentary edits, a C11 DRAFT render of kind close_package composed by code; DRAFT watermark and per-page legend by C11), PackageAssemblyWorkflow (waits for the render job, ends the DET run), compose_package, byte-stable XLSX, page URL
- migration 0993 adds close_package to generated_documents.kind and report_templates.family; GeneratedDocumentKind literal
- routes generate, pages/{n}, package.pdf (303 to P-03 content), package.xlsx
- closes WORKFLOWS/ACTIVITIES; replay recorder record_s52_package.py (history recorded at the end pass); reviewed audit actions
- unit tests test_c02t28_package_render.py

## Progress log
- `2026-11-20` — Plan (amber): render module, workflow, migration, routes, recorder, tests; rollback revert + downgrade 0993. Byte-identical PDF render proven at the end pass on the render worker.
