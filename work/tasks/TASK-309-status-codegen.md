---
id: TASK-309
title: "F-03-T09: status codegen (C2) — kernel StrEnums and CHECK lists, and the UI registry, generated from status-vocabulary.yaml"
spec: SPEC-306
acceptance_criteria: [AC-2]
risk_zone: red
status: done
branch: task-309-status-codegen
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
- `abacus_tools/codegen/status_vocabulary.py` validates the registry:
  - codes are snake_case;
  - every code has label, variant, terminal and derived;
  - no `match` variant;
  - labels are sentence case, not Title Case.
- It generates two files:
  - `kernel/_statuses.py`: a StrEnum per object holding the stored codes, plus `CHECKS`;
  - `packages/ui/src/status.gen.ts`: the UI registry, which prettier ignores.
- It's added to `GENERATORS`, so `check-generated` (in check-fast) fails on drift.
- The UI gains `registryWord(object, code, {client, fill})` and `STATUS_REGISTRY`.
  - The legacy `STATUS` map stays until request status v2 (T15).

## Not in this task
- Serialising API statuses as `{code, context}`. This comes with each object's migration: requests in T15, engagements in T12.

## Definition of done
- [x] `tests/unit/tools/test_status_vocabulary.py` (6) and `src/gallery/statusRegistry.test.ts` (3) pass; check-fast passes.
