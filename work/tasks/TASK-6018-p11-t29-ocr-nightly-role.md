---
id: TASK-6018
title: "P-11-T29 the OCR nightly role in Terraform: GitHub OIDC from one environment, two Textract actions"
spec: SPEC-000  # row (P-11-T29)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T29
branch: s29m-p11-t29-ocr-role
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-08
updated: 2026-11-08
---

## Objective
ocr-nightly.yml skips until vars.OCR_NIGHTLY_ROLE_ARN names a role; no role existed in code. Write it so the variable can be set from a plan, not by hand in the console.

## Plan
infra/envs/staging/ocr_nightly.tf: deploy-role module (OIDC trust from the ocr-nightly GitHub environment only), policy allowing textract:DetectDocumentText and AnalyzeDocument in the staging region and denying every other action; count on textract_enabled. Output ocr_nightly_role_name (the ARN is composed outside git). ocr-nightly.yml job declares environment: ocr-nightly. Offline test infra/tests/test_ocr_nightly_role.py. Not applied. Rollback: revert.

## Progress log
- 2026-11-08: built. infra/tests test_ocr_nightly_role (4), test_textract, test_repository_files: 23 passed; terraform fmt and validate clean (staging, -backend=false).

## Decisions made during this task
DEC-2614
