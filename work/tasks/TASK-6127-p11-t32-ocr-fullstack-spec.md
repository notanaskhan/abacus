---
id: TASK-6127
title: "P-11-T32 full-stack OCR notice intake spec for staging"
spec: SPEC-000  # row (P-11-T32)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: P-11
plan_key: P-11-T32
branch: s30-p11-t32
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Full-stack E2E `ocr-notice-intake.fullstack.spec.ts` on staging with Textract on synthetic documents: Santos CP14 photo upload, OCR, NOT-01 intake with SHL-08 regions.

## Plan
- `apps/web/e2e/documents/ocr-notice-intake.fullstack.spec.ts` on the harness projects (axe and invariants per step): NOT-01 shows the synthetic CP14's notice number, tax year and amount due; a field opens SHL-08 with its region and the OCR text-source layer; nothing is created until a person confirms. Fixme on fixture; skips without `ABACUS_E2E_SANTOS_CP14_UPLOAD`.

## Progress log
- 2026-11-08: built. Written, not run (needs staging with Textract). eslint and prettier clean.

## Decisions made during this task
None.
