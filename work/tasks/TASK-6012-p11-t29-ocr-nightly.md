---
id: TASK-6012
title: "P-11-T29 the nightly real-Textract OCR run, report-only until two passes; stack gate fixes"
spec: SPEC-000  # row (P-11-T29)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T29
branch: s29l-p11-t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
The CI run blocks merges, and the nightly real run is report-only for two weeks and then blocking once two consecutive runs pass.

## Plan
abacus_tools/evals/ocr_extraction.py: the suite's metrics over any OCR provider (FakeOcr for CI's code path, TextractOcr for the nightly), a verdict against suite.yaml, a JSON report, exit 0 when report-only and 1 on a failed blocking run. .github/workflows/ocr-nightly.yml: daily, OIDC into the staging role named by vars.OCR_NIGHTLY_ROLE_ARN (skipped without it), --blocking once vars.OCR_NIGHTLY_BLOCKING is true, the report as an artifact; actions pinned to the repo's SHAs. The CI test is unchanged and gains: the runner scores the fake run as the test does; report-only exits 0, blocking 1. Stack gate fixes found by a whole-tree banned-patterns run: CLOCK-001 in refdata_rollover (T-03-T18, #1386: kernel `today`), BOUND-001 in the two recorders (Q-03-T195, #1390) and this runner (module apis now re-export the workflows, inputs and evidence helpers they read), SKIP-001 on A-06-T32's strict xfail (#1388: TASK reference). Rollback: revert; the workflow is inert without its variable.

## Progress log
- 2026-11-07: built. tests/unit/evidence/test_ocr_extraction_suite.py (9), the replay tests, A-06-T32 and the preflight pass (33 and 1 strict xfail); banned patterns clean over the whole tree; test_f04t36_independent's clock check passes. Not run: the nightly itself (needs the staging role).

## Decisions made during this task
DEC-2610
