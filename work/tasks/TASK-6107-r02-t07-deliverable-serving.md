---
id: TASK-6107
title: "R-02-T07 deliverable serving: watermarked pages, single-use 60-second links, audience check, A-06's C18 port wired"
spec: SPEC-000  # row (R-02-T07)
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: R-02
plan_key: R-02-T07
branch: s30-r02-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
R-02 §3.15 (AC-38 to AC-41): evidence.api deliverable serving (pages with the burned-in DRAFT mark, a 60-second single-use download link, an access_events row per request, the audience check through reporting.api) and the adjustments registry line wiring A-06's C18 port to the slot.

## Plan
- Migration 0712 on 0711: `deliverable_download_links` (evidence): server-set 60-second expiry, issued to the session's actor (CHECK), used once (trigger), never deleted, forced RLS.
- `reporting/deliverable_reads.py`: `reader_version(ctx, deliverable_id, version_no)` (client humans only; published, unwithdrawn; an active grant covering an audience by role and scope, DEC-93; a draft must be a C11 draft-mode render) and `ReaderVersion.servable()`.
- `evidence/deliverable_serving.py`: `ServableVersion`, `deliverable_page`, `issue_deliverable_download`, `open_deliverable_download`; access kinds `deliverable.page_view`, `deliverable.download` (tri-marked for tax kinds); audit `deliverable.download_issued`, `deliverable.downloaded`.
- `engagements/client_approvals.py`: `ClientApprovalRequested`, `ClientApprovalDecided`, `deliver_proposed_entries` (at-least-once safe); `adjustments/api.py` registers it with `register_client_delivery`.
- Tests: `tests/unit/reporting/test_r02t07_reader_audiences.py`, `tests/unit/evidence/test_r02t07_deliverable_serving.py`, `tests/integration/test_r02t07_download_links.py`.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean.

## Decisions made during this task
DEC-2705
