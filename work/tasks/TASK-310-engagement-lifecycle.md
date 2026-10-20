---
id: TASK-310
title: "F-03-T12 [mig 0069]: engagement lifecycle — 14 types (audit → fs_audit), service line, 8 lifecycle codes, gate policy"
spec: SPEC-306
acceptance_criteria: [AC-3]
risk_zone: red
status: done
branch: task-310-lifecycle
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
- Migration **0069**:
  - the type CHECK takes the 14 types; `audit` is rewritten to `fs_audit` in engagements, methodology templates and assurance work items;
  - `service_line` is set by a BEFORE INSERT trigger from the type; `office_id` and `standards_set_id` are added;
  - the status CHECK takes the registry's 8 codes;
  - the 0068 trigger now creates the assurance item for attest families only (the primary entity always);
  - new `gate_policy_overrides` table (insert-only).
- `engagements/gate_policy.py`: platform gates per family; firm overrides can only add.
- `EngagementType` takes the 14 types. `EngagementSummaryOut.status` uses the generated `EngagementStatus`, and the summary gains `service_line`.
- Web:
  - `engagementTypes.ts` takes its types from the generated client, offering 6 attest types at creation and labelling all 14;
  - test fixtures follow.
- Rollback: downgrade 0069, which rewrites `fs_audit` back to `audit`.

## Definition of done
- [x] Local data: 52 engagements now read `fs_audit` / `audit` / `active`.
- [x] up/down/up passes (schema_check).
- [x] Engagement unit and integration tests (284) pass, including a new tax-engagement case and `test_gate_policy.py`.
- [x] All 319 screen tests pass.
- [x] check-fast passes.

## Progress log
- 2026-10-20: `tests/integration/test_engagements.py` expected the old summary keys; it now includes TASK-304's client ids, which the integration run hadn't caught at the time.
