---
id: TASK-2430
title: T-02-T26 Portal K-1 endpoints (POR-13)
spec: SPEC-502
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: T-02
plan_key: T-02-T26
branch: t02-t26-portal-k1
worktree: /Users/ayushkbhatia/Accrued/abacus-s19b5
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Portal K-1 endpoints: list and detail of own released packages, deterministic zip and single
document downloads with access events, Viewed and Downloaded events, details-change submission,
electronic-furnishing consent, bounce subscriber.

Acceptance: "Pell Street Ventures' member cannot read Pell Street II's package and every download
writes an access event."

## Plan (amber)
- `tax/k1_portal.py`; the portal routes in `k1_contract.py`; `message.bounced` in `k1_release.py`.
- Stacked on T-02-T21 (#937): the `k1_package` scope resolver and the release's grants.
- Tests: `tests/integration/test_t02t26_portal_k1.py` (end review).
- Rollback: revert; the routes answered 501.

## Progress log
- `2026-10-31` — Built on `t02-t26-portal-k1` (on `t02-t21-k1-release`). DEC-1478. Tests run in
  the end review.
