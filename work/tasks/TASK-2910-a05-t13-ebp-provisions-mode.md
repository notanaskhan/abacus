---
id: TASK-2910
title: A-05-T13 mode ebp_provisions (prompt, provision registry, code comparison)
spec: SPEC-640
acceptance_criteria: [AC-11]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T13
branch: s24-a05-t13 (stacked on s24-a05-t12)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

The `ebp_provisions` mode's own prompt, the twenty-provision registry on the EBP-02 paper, and the code comparison for SPD conflicts and amendment governance.

## Acceptance (backlog)

On the Northwind documents the mode proposes 20 provisions (18 for Version 1), flags the SPD quarterly-entry conflict and the Jan 1, 2025 catch-up amendment, and every quote verifies.

## Plan

- Prompt `workpapers.section_draft_ebp_provisions@v1`; spec v3 points `ebp_provisions` at it (output stays `SectionDraft`: each provision is cells B<row> and C<row>, each citing D1 adoption agreement, D2 amendment or D3 SPD with the exact clause words, verified by the workflow's C4 check).
- `assurance/compute/ebp/provisions.py` (pure): the twenty provisions in the design's order on rows 2-21, the two amendment-governed ones (eighteen without the amendment), `governing` (the amendment from its effective date, never the SPD), `normalise` and `conflicts`.
- Deferred to EBP-02's service (DEC-1957): mapping the run's adopted cells into `ebp_provisions` rows (one plan-review version per document set) and the conflicts into `ebp_provision_conflicts`; the D1-D3 document mapping for the mode's context.
- Test: `tests/unit/assurance/test_a05t13_provisions.py`.

## Progress log

- 2026-11-01: built in abacus-s24, stacked on A-05-T12. Tests written, not run.
