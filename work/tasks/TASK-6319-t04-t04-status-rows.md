---
id: TASK-6319
title: T-04-T04 status registry rows and codegen (C2)
spec: SPEC-649
acceptance_criteria: [AC-1]  # the YAML generates StrEnums, OpenAPI enums and status.ts; exhaustiveness holds
risk_zone: amber
status: done
epic: T-04
plan_key: T-04-T04
branch: s32-t04-t04
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
C2 rows for the return workspace: document approval, field view, K-1 activity, K-1 treatment,
residency determination, assistant availability.

## Progress log
- `2026-11-09` — Six objects added to `status-vocabulary.yaml`; `kernel/_statuses.py` and
  `packages/ui/src/status.gen.ts` regenerated. Tests not run (end pass). New labels not in the
  handoff's status.js word list are T-04's own (SPEC-649); the handoff-word check may need them
  listed under `handoff_words` at the end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3019 | Object names, codes and variants; derived flags | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status done.
