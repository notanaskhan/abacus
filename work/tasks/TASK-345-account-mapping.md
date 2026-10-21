---
id: TASK-345
title: "A-03 mapping core and AUD-20 draft statements: FS groupings import and publish, account mapping, statements by code"
spec: SPEC-316
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7]
risk_zone: red
status: done
branch: task-345-mapping
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan
- **Migration 0079:** seven tables and the publication freeze trigger. Rollback is the downgrade.
- **Ledger:**
  - `mapping.py`: `parse_taxonomy`, `rule_line`, `build_statements`, `content_hash`, and the service;
  - `mapping_repository.py`;
  - models and registry;
  - api exports.
- **Assurance:**
  - `mapping.py`: authorise (firm-level for groupings), sign the mapping, and the mapping-set reviewable;
  - `mapping_routes.py`, with the `firm_router` for `/v1/grouping-sets` and the trial-balance router;
  - matrix actions `grouping_set.import`, `grouping_set.publish` and `mapping_set.edit`.
- **Web:** `GroupingSets.tsx` (Settings › FS groupings) and `TbMapping.tsx` (`TbMapping` and `TbStatements`), plus the TrialBalance view toggle.

## Progress log
- Glossary (A-03-T01's rows): adds Grouping set, Grouping, FS line and Mapping set, and narrows Fulfilment's `mapping` ban to `evidence_mapping` and `request_mapping` ("mapping" now names only mapping sets). The firm-wide `account` ban stays, so the edits table is `mapping_set_edits`, not the plan's `account_mappings`. The new `taxonomy` ban caught this task's own `Taxonomy` class, renamed `ParsedGroupingSet`.
- Dev firm smoke test:
  - A draft with an overlapping range lists `overlapping_range`; the clean draft publishes; republishing is refused.
  - The dev trial balance's 32 accounts all map by range.
  - The statements balance (assets 39,291,295.66 = liabilities 3,769,638.00 + equity 35,521,657.66).
- The smoke test left the "Smoke FS groupings" content in the dev firm (v1 with problems, v2 published), plus a mapping on the dev trial balance, for the UI walkthrough.

## Definition of done
- [x] `tests/unit/ledger/test_mapping.py` (6), the ledger tests and the pinned gate tests pass.
- [x] spec316mapping and spec309 (13) pass.
- [x] check-fast passes.
