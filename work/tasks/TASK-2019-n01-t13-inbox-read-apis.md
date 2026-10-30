---
id: TASK-2019
title: N-01-T13 Inbox read APIs
spec: SPEC-380
acceptance_criteria: [AC-25]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T13
branch: s15n-n01-t13
created: 2026-10-29
updated: 2026-10-29
---

## Objective
The firm Inbox's summary, threads list, thread detail with field gating, the masked viewer
manifest, audited content and Download All, match-client with remember sender and ignore thread;
`waiting_for_work_item` for T-02 and HOME-01's `inbox_waiting` (DEC-1059).

Acceptance (backlog row): "Counts exclude walled clients without disclosing them and every
content read writes an audit event."

## Built
- `communications/inbox_read.py`; routes live in `intake_contract.py`; `api.py` exports and the
  home count; evidence `intake_masked_pages`. Stacked on N-01-T12 (`inbox_attachment_id`).
- Stub test's live paths updated; OpenAPI and client regenerated.

## Tests
Build-only (Ayush, 2026-10-29): no tests written or run; at the end review.

## Progress log
- 2026-10-29: built (S15 group B, build-only). ruff, pyright, lint-imports clean.
