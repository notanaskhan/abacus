---
id: TASK-8912
title: "T-06-T43: Form-face content, part 1"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-t06t43
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-06-T43
---

## Objective
Form 1065 pages 1-5 (incl. Schedules B, K, Analysis of Net Income, L, M-1, M-2) and Schedule K-1 (1065) for TY2025 and TY2028 as database report templates (kind tax_form_face) with field manifests, loaded through P-11's import endpoint; never committed as seed. Acceptance: each template validates against the field-manifest schema, and the import dry-run diff is empty on a second load.

## Done
- C11 v1.2 additive: family/kind and layout tax_form_face; FieldManifestIn (pages, fields with box, format, binding, mask) on TemplateImportIn; import validation (field_manifest_required / field_manifest_invalid by path); the manifest in content_sha256; ImportReportOut.changes (dry-run diff against the latest version via methodology.latest_report_template_content)
- Migration 1015: kind/family and layout CHECKs widened; report_template_versions.field_manifest (present exactly for the tax_form_face layout) + insert grant; methodology stores and returns it (TemplateBundle, version_parts)
- abacus_tools/form_faces.py: validates every draft locally, dry-runs each through the import endpoint and with --apply imports only changed ones (a second run: no change)
- Content (not in the repo): /Users/ayushkbhatia/Accrued/refdata-drafts/ty2025 and ty2028: tax_form_face-1065 (163 fields, 5 pages) and -1065-k1 (34 fields), generated from the form-line drafts; all four validate with 0 problems (python -m abacus_tools.form_faces --dir …)
- docs/contracts/c11-renderer.md v1.2 note; tests/unit/reporting/test_t06t43_form_faces.py (12 pass)

## Progress log
- `2026-11-23` — Built in the S53 sequential stack (DEC-5914). Human remainder: load the four drafts into each firm through the import endpoint (python -m abacus_tools.form_faces --dir … --base-url … --apply) and publish them (a different person); TY2028's line set mirrors TY2027's until the IRS publishes the TY2028 forms (re-run the generator then).

## Plan (amber)
1. C11 additive schema + validation + dry-run diff; migration 1015; methodology storage.
2. Content drafts outside the repo; an operator loader. 3. Rollback: downgrade drops the column and narrows the CHECKs (NOT VALID).
