---
id: TASK-7618
title: P-02-T09 independent AC tests (ADR-078) for P-02-T05 to T08
plan_key: P-02-T09
spec: SPEC-000  # C15 v1, docs/contracts/c15-search.md; ADR-241
acceptance_criteria: [AC-1]  # written from the contract and spec; passes once T05-T08 land, without edits by the implementing session
risk_zone: red
status: in-review
branch: p02-t09-independent
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The independent acceptance suite for the search index and query (ADR-078 as amended for one
builder: written from `docs/contracts/c15-search.md`, ADR-241 and P-02 §3, not from the code).

## Plan
- `backend/tests/integration/test_p02t09_search_independent.py`: walls (no row, no count, no
  suggestion; identical to a corpus without the document), need-to-know, query-time wall, every
  result opens (`authorise()` on each row), offshore TRI (refused rows neither shown nor counted),
  client roles and the agent refused, withdrawal deletes, PII scrub, RLS across firms, a sentinel
  search text absent from logs and output, no agent run from the palette.
- Q-03-T271 (ADR-078 catch-up lane): this suite is its S40 share for P-02.
- Rollback: delete the file.

## Progress log
- `2026-11-12` — Suite written from the contract. Runs at the S40 end pass; a failure is fixed in
  the implementation, never by editing this suite (the end pass records any edit here as a finding).
