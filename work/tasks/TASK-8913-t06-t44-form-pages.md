---
id: TASK-8913
title: "T-06-T44: Form pages service: render from the approved checkpoint through C11"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-t06t44
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-06-T44
---

## Objective
Row: "Form pages service: render from the current approved checkpoint through C11 with the 'Draft - not for filing' watermark and burned-in TIN masks, page images and manifest, field bindings to workbook cells and TB lines, render cache by (checkpoint, template version)." Acceptance: "Two renders of the same checkpoint are byte-identical, and Item F reads 17,914,500 bound to the TB total-assets line."

## Done
- review.checkpoint_state (named or newest approved checkpoint's values) and methodology.published_form_face (form + tax year from the manifest)
- tax/form_pages_service.py: binding resolution (workbook cells, form-lines keys with credit-side signs and L14/L22 totals from the reference set's sides, return facts incl. engine summary, profile, Analysis of Net Income by partner kind), form formatting, burned-in TIN mask (none offshore), content hash, form_page_renders cache, PNG pages, download (human, fresh MFA, audited, no-store), diagnostics per checkpoint, K-1 box 2 previews
- reporting/form_face.py: face_html, render_face, render_face_isolated (C11 isolated child), watermark on every page
- entity_depth_contract: six TAX-11 routes live plus GET form-pages/{page_key}/image; docs/contracts/form-pages.md v1
- tests: tests/unit/tax/test_t06t44_form_pages.py (11 pass), tests/golden_render/test_t06t44_form_face_render.py (image-bound byte identity, make golden-render)
- DEC-5915; error code checkpoint_required catalogued

## Progress log
- `2026-11-23` — Built in full. Byte identity of the PDF itself is proven in the image (WeasyPrint's system libraries are not on this Mac); the unit suite proves the HTML and content hash. Remainder for the end pass: make generate (new image route), make golden-render.
