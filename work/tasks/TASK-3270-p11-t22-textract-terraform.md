---
id: TASK-3270
title: P-11-T22 Terraform for Textract (endpoint, worker policy, alarms, budget, quota requests)
spec: SPEC-000  # row; P-11 §7
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T22
branch: s27-p11-t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"From the worker task Textract is reachable only through the endpoint in us-east-2, any other
Textract action is denied, and a Terraform test fails if the opt-out policy is detached."

## Plan (red)
- `infra/modules/textract`: interface VPC endpoint (private DNS, HTTPS from the worker tasks'
  security group only); worker role policy allowing `DetectDocumentText` and `AnalyzeDocument`
  with `aws:SourceVpce`, denying every other Textract action and any Textract call outside the
  endpoint; throttle and error alarms; a monthly cost budget; quota increase requests as reviewed
  inputs.
- `infra/envs/staging/textract.tf` behind `textract_enabled` (default off until the provider
  terms entry is approved, DEC-2217); variables for the budget and quota codes.
- Tests: `infra/tests/test_textract.py` (offline, from the source and the landing-zone opt-out).
- Not here: applying it (Ayush with AWS credentials), production wiring (the production env has
  no worker yet), the actual quota codes for the x100 test (Q-03-T160).

## Progress log
- 2026-11-04: built; `terraform fmt -check` clean.

## Decisions made during this task
DEC-2250.
