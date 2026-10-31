---
id: TASK-2429
title: T-02-T23 Seed T-02 content through import endpoints
spec: SPEC-502  # the backlog row; T-02 §5
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: T-02
plan_key: T-02-T23
branch: t02-t23-tax-content
worktree: /Users/ayushkbhatia/Accrued/abacus-s19b5
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Seed POR-05, TXP-12 and POR-13 content through import paths: organizer template and answers
(22 of 24), Kevin's team question, Dana's four inquiries, Luis's two questions, Ridgeline (5),
Bluestem (2) and Calloway (2) K-1 sets with hand-offs, portal users for Nora Calloway and the Pell
Street member.

Acceptance: "Every POR-05, TXP-12 and POR-13 figure foots in seed tests and no content is loaded by
a migration."

## Plan (amber)
- Slice `tax_content` (`tax_content.py`), loader handlers through `tax.api` / `requests.api` /
  `organisations.api` service functions.
- Fix: `k1_set` JSON manifest stored with `stage_content` after the strict isolated parse.
- Tests: `tests/unit/synthetic/test_t02t23_tax_content_slice.py`,
  `tests/integration/test_t02t23_tax_content_load.py` (end review).
- Rollback: revert; the slice is opt-in.

## Progress log
- `2026-10-31` — Built on `t02-t23-tax-content` off main 71d2e51d2. DEC-1477. Load test runs in
  the end review (builds first, per Ayush). Sep 15 release snapshot deferred (DEC-1474's owed
  final-approval seed path).
