---
id: TASK-9017
title: "T-06-T49: Form-face content part 2 and TAX-11's attached forms"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-t06-t49-attached-forms
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: T-06-T49
---

## Objective
Backlog row acceptance: "Thumbnails show every page in TAX-11's list, and a page without a template shows the placeholder rather than a blank." Content: Schedule M-3 pages 1-3, Form 8825, Form 4562 summary page, section 199A and section 754 statements for TY2025 and TY2028 as database templates through the import endpoint.

## Done
- form_pages_service: TAX-11's list is the face's pages then the return's attached forms in the handoff's order (ATTACHED; M-3, Sch. C and 8916-A at total assets >= 10,000,000; 754 statement on a transfer of interest), each from the firm's own published face, keys prefixed with the form
- An attached form without a published template is a placeholder page (additive placeholder: true on TaxDepthFormPageOut): no fields, no image, never cached, rendered or downloaded
- Fixed a T-06-T44 defect: the page cache's unit of work recorded no audit event, so a first GET form-pages failed on Postgres; now form_preview.rendered on a first render, nothing on a re-read
- Content outside the repo: refdata-drafts/ty2025 and ty2028 tax_form_face-{1065-m3,8825,4562,1065-199a,1065-754} (generator _s54tools/form_faces_part2.py); all validate with abacus_tools.form_faces
- Tests: tests/integration/backfill/test_t06t49_attached_forms.py (Postgres) and tests/golden_render/test_t06t49_attached_render.py (image-bound, make golden-render)
- API client regenerated; docs/contracts/form-pages.md section; DEC-6023

## Progress log
- `2026-11-27` — Built; Postgres test passes with the T-06-T44 unit suite. Human remainder: load the ten drafts into each firm (python -m abacus_tools.form_faces --dir ... --base-url ... --apply) and publish them (a different person). The golden-render test runs in the image at the end pass.
