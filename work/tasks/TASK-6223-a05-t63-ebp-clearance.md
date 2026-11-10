---
id: TASK-6223
title: A-05-T63 clearance path for the EBP modes
spec: SPEC-640
acceptance_criteria: [AC-1]  # a signed passing run for every EBP mode, or synthetic-only with the gap in the decision log
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T63
branch: s31-a05-t63
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan (red: written before building)
- No real run: the provider-terms register has no approved Bedrock entry (ADR-114), and a
  full-suite real run costs money (`make evals`). So the row's alternative holds: the modes stay
  synthetic-only and the gap is recorded (DEC-2818).
- Files:
  - `evals/workpapers_section_drafter/clearance.yaml` (no mode recorded);
  - `docs/operations/section-drafter/ebp-clearance.md` (the path and the PW4 shadow plan);
  - `backend/tests/unit/agents/test_a05t63_ebp_clearance.py`, which keeps `client_data` at `none` until every mode is recorded from a signed report that exists, and holds the decision-log gap while uncleared.
- Spec unchanged (`client_data: none`). Rollback: delete the three files and the DEC row.

## Partial
- The signed Bedrock run itself needs approved provider terms and the founder's go-ahead to
  spend; it is the open clause.

## Progress log
- 2026-11-08: recorded; the test runs at the S31 end pass.
