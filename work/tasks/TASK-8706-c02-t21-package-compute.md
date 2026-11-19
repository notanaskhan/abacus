---
id: TASK-8706
title: "C-02-T21: Package compute and preconditions; GET and PATCH package"
spec: SPEC-701
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: c02-t21-package-compute
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: C-02-T21
---

## Objective
closes/compute/package.py (pure): posted TB from posted or recorded entries, statement lines through C9's FS lines with per-figure lineage, balance sheet (derived YTD net income), income statement against the prior month, cash flows YTD (indirect, tied to cash), AR/AP agings tied to their control accounts, CLS-08c preconditions, the SSARS route from K-02's ssars_framework_for and the CAS answer, commentary from accepted flux, content hash. package_service.py serves GET and PATCH /closes/{id}/package.

## Plan (amber)
1. compute/package.py with exact-Decimal goldens tests/golden/closes/test_c02t21_package.py (549,195.45; 27,795.00 vs 31,455.00; 18,420.00; 21,380.45; Aug 31 → AR-C 70 + legend; Dec 31 → CAS by-product).
2. package_service.py: read deliverable + latest version; figures from C8 final layer and C9 mapping_view; preconditions from close_summary and pending entries; PATCH writes an insert-only version at the version seen (StaleClose) and refuses a released package (package_released, new code in error-codes.yaml and delivery_errors.py).
3. methodology api exports SsarsCasSettingsPayload.
4. delivery_contract: the two routes call the service (shapes unchanged; no client regeneration).

## Progress log
- `2026-11-19` — Built; goldens pass (8). Partial: commentary is not filled into the version yet (the library fills a template; the firm's commentary template content and CLS-08's commentary route are C-02-T23/T28), and the C9 CAS catalogue ordering uses the grouping set's own order. DB-backed route test at the S51 end pass. Gates and tests run once at the S51 end pass (build first, test last).
