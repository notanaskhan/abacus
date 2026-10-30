---
id: TASK-5010
title: "Mapping staleness: mapping_set.went_stale on a new trial balance version"
spec: SPEC-316
acceptance_criteria: [AC-9]
risk_zone: red
status: done
branch: task-5010-mapping-stale
worktree: agentwt
created: 2026-10-30
updated: 2026-10-30
---

## Plan keys
A-03-T14 (partial: staleness and the event; auto-creating the set on version 1 waits for a firm-default grouping set).

## Plan
- **`assurance/mapping.py`:**
  - the `MappingSetWentStale` event;
  - `went_stale_id(mapping_set, version)`;
  - `on_tb_version`, subscribed to `trial_balance.version_created`, emits once per version when `review.stale_of` finds the mapping's sign-offs off the current hash. A duplicate event id means a replay.
- **`review/stale.py`:** `STALE_SOURCES` gains `mapping_set.went_stale` → (`mapping_set`, `mapping_set_id`). The existing detector then tells the signers through `sign_off_stale`, so no new C16 kind is needed yet. The plan's `mapping_set_stale` kind belongs to ayushkbhatia and can consume the event later.
- **`assurance/api.py`:** `SUBSCRIPTIONS` merges phase and mapping.
- **Rollback:** revert the PR. There are no migrations.

## Notes
- Running the classification test locally needs Pango (`brew install pango`). WeasyPrint arrived with P-11, and it fails to import without that system library. That's an environment gap on this machine, not this change.

## Progress log
- test_mapping_stale (6) and the assurance and review unit suites (118) pass.

## Definition of done
- [x] Targeted tests pass.
- [x] check-fast passes.
