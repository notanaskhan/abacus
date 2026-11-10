---
id: TASK-6724
title: "T-04-T23: return issues (sources, category paths, Draft K-1 system resolution, CSV), checkpoint chip, tax ACTIVITY_KINDS and the work-item activity filter"
spec: SPEC-649
acceptance_criteria: [AC-4.1, AC-4.2, AC-4.7, AC-5.1, AC-5.2, AC-5.6]
risk_zone: amber
status: in-review
branch: s35-t04-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: T-04-T23
---

## Objective
Feld shows 4 open issues (2 Missing information, 1 Action required, 1 Review point) and 3 resolved, the Draft K-1 issue resolves only when the K-1 is released, and the activity read lists 24 events newest first with 'via Agent' attribution.

## Plan (amber: written before the build)
- **Migration 0800** (`issue_sources_system_resolution`, on 0790):
  - `issues` gains `source_kind`, `category_path` and `system_resolved_only` (a dependency only), all insert-only.
  - `issue_events` gains the `system_resolved` event (system actor only).
  - The trigger `issue_events_system_only` refuses a person's `resolved` or not-applicable event on a system-resolved issue, and a `system_resolved` event on any other issue.
- **`review` (P-04 additive):**
  - `IssueSource` on `create_issue`; `IssueRow` carries the three fields.
  - `move` refuses with 409 `system_resolved_only`.
  - `system_resolve_dependents(system, source_ref)` (system only, one audit event `issue.system_resolved` each).
  - Exports: `list_issues`, `read_issue`, `list_checkpoints`, `OPEN_STATUSES`.
- **`tax/return_issues.py`:**
  - Category paths.
  - `raise_draft_k1_issue`: Action required, High, blocks final approval and export, system-resolved only, `source_ref k1_dependency:<package>`.
  - The `k1_package.released` event (new, emitted when a package is released in `k1_release`) and its consumer, which resolves the dependents as the system.
  - `issue_counts`, `issues_csv` (`export.create`, formula-escaped cells, `export.created`) and `checkpoint_chip`.
- **`tax/workspace_contract.py`:** RW-1's summary now carries `issues_open` and `checkpoints_proposed`, and `GET /v1/tax/returns/{id}/issues/export` streams the CSV.
- **`tax/activity_kinds.py`:** the tax actions' catalogue entries and AUD-29 links (registered at import), TAX-07's groups (approvals, client, agent, tax_engine, issues), and `title` ("{Verb} by {Actor}", "… by <person> via Agent", "by Accrued Agent" for proposals and self-checks only; an agent decision reads neutrally).
- **`audit_trail`:** `ActivityFilter.work_item_id`, which the query and export bodies carry (AC-5.6); `ActivityLink` and `register_activity_links` exported.
- **Registry:** error code `system_resolved_only`.
- **Tests:**
  - `tests/unit/tax/test_t04t23_activity_and_issues.py`.
  - `tests/integration/test_t04t23_return_issues.py`: 4 open by kind and 3 resolved, the Draft K-1 refused for a person in the service and the database, resolved by the system on release, and the chip.
- **Rollback:** revert. 0800 is expand-only, and its downgrade drops what it added.

## Partials (flagged)
- **"24 events newest first":** needs T-04-T28's whole Feld timeline, so it is not asserted here. The filter, kinds and titles are built and unit-held.
- **Ask the client with options:** `issue.send_to_client` already exists (P-04-T31), but the request item has no options field (R-01's POR-04 options). The options half waits on an R-01 contract change.
- **Raising the Draft K-1 issue:** the receiving side (T-05's K-1 hand-off into the 1040) does not call `raise_draft_k1_issue` yet.
- **Contract change:** the activity bodies gain `work_item_id` and there is a new CSV route, so `make generate` runs at the end pass.

## Progress log
- 2026-11-10: built; migration head 0800 on 0790 (re-check heads before merge); tests at the end pass.
