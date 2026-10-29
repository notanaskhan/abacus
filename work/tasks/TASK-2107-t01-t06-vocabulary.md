---
id: TASK-2107
title: T-01-T06 Protected glossary and status-vocabulary rows (DF-31)
spec: SPEC-501
acceptance_criteria: [AC-12]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T06
branch: s16-t01-t06
created: 2026-10-29
updated: 2026-10-29
---

## Objective
The T-01 glossary rows, the consent, authorization, sync-chip and ack status objects, and a copy
ban on "Accrued transmits" (T-01 §4.9; DF-31).

Acceptance (backlog row): "The glossary PR merges with your approval, C2 codegen emits the new
codes, and the copy lint rejects 'Accrued transmits'."

## Plan
- `docs/product/glossary.md` (nine rows); `docs/product/status-vocabulary.yaml` (four objects);
  status codegen; pins in `apps/web/src/status/status.test.ts`.
- `apps/web/src/copy-bans.test.ts`.

## Progress log
- 2026-10-29: built (S16 block; tests run at the batch's end review). DEC-1157.
