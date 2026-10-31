---
id: TASK-2423
title: T-02-T20 K-1 package core
spec: SPEC-000  # the backlog row; T-02 §3.6, §5; DEC-78, DEC-88
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: T-02
plan_key: T-02-T20
branch: s19-t02-t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Migration for recipients, packages, events, documents, box lines, hand-offs and recipient-details
changes; applying approved CCH k1_set imports (draft or final, supersede after release); list with
tiles and expanded rows; share internally with DEC-88 visibility, internal_handoff evidence copy
and dependency; release-check read; resend; details-change review.

Acceptance: "Shared Ridgeline drafts block Feld final approval and no client principal can reach
a draft package or document."

## Plan (amber)
- Migration `0565_k1_packages` (on 0564): seven tables, grants, the decided-once trigger, and
  `engine_sync_events.kind` + `k1_set`. Downgrade drops them and restores the kind check.
- `tax/k1_packages.py`; bridge kind `k1_set` (`engine_import`, `engine_contract`) and suffixed
  K-1 PDF names (`engine_adapter`); routes live in `k1_contract.py`; `draft_k1` blocker
  registered in `tax/api.py`; TAX-02 dependency rows in `overview.py`.
- `evidence.file_handoff_copy`, `requests.k1_request_for`.
- Tests: `tests/integration/test_t02t20_k1_packages.py` (end review).

## Progress log
- `2026-10-31` — Built on `s19-t02-t20` off main 7d4def8e5; 0565 revises 0564 (#908): merge after
  #903 and #908. DEC-1471. TAX-03's `k1_handoffs` wiring waits on T-02-T18 (#914) merging.
