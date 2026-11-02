---
id: TASK-2901
title: A-04-T13 risk register service (AUD-05, AUD-08)
spec: SPEC-620
acceptance_criteria: [AC-19, AC-20, AC-21]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T13
branch: s24-a04-t13 (stacked on s24-a04-t12)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

A-04 §3.4: the risk register behind AUD-08 — create and edit risks through the field history, RMM by code from the firm's RMM matrix, the tally, linkage and responses, the coverage check, the `risk` suggestion applier, and the presumption rules.

## Acceptance (backlog)

The Northwind tally reads 10 / 2 (+1 proposed) / 2 / 3 / 1 from the grid, a rebuttal on R1 returns 422 presumption_not_rebuttable, and the coverage check returns 10 of 10 with R8 unaddressed.

## Plan

- **Migration `0640_threshold_policy_rmm_matrix`** (expand-only, on 0614): `threshold_policies.kind` CHECK admits `rmm_matrix`.
- **Methodology (K-02).** `RmmMatrixPayload` (`rows: [{inherent_risk, control_risk, rmm}]`, the import's Rows sheet), the `StandardPayload` union, `rmm_for` and `methodology.api.rmm_matrix_for(tenant, ir, cr, as_of)` (no matrix: `LookupError`; no row: `standard_row_missing`). KNW-04's switch shows no section for it.
- **BH seed.** BH matrix v1 (`bh-rmm-matrix`, owner MO) created, imported and published in the sampling slice beside Table 2; CR Max leaves IR as RMM.
- **Review.** `review.api.field_timeline` (a field's versions, oldest first) for the drawer's versions.
- **Service `assurance/risks.py`.** Create (next code; management override reads Mandatory; presumed fraud reads Presumed), edit (version check, presumption rule, RMM recompute, every changed field through `record_value`, new content hash, `ep_approved` rows go `revised`), register with tally and register hash, drawer (citations and suggestion of the latest rationale; versions from the field history), linkage (planned workpaper targets until a built audit section registers them), link and unlink (removed_at), coverage (TB areas at or above PM against risk areas; unaddressed = no live link), the `risk` suggestion applier and engagement lookup, audit owners (`risk_register_row`, since SPEC-300 holds `risk`).
- **Contract.** `POST /risks/register` (additive, `RiskCreateIn`); register, linkage, coverage, drawer, edit, responses live.
- **Tests.** `tests/integration/backfill/test_a04t13_risk_register.py`.
- **Rollback.** Flag `assurance.risk_register` off; the migration's downgrade restores the CHECK.

## Decisions

DEC-1951.

## Progress log

- 2026-11-01: built in abacus-s24, stacked on A-04-T12 (coverage reads the in-force PM). Tests written, not run.
