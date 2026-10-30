---
id: TASK-2328
title: N-02-T30 SIG-02 part 2 (field placement)
spec: SPEC-381
acceptance_criteria: []
risk_zone: green
status: in-review
epic: N-02
plan_key: N-02-T30
branch: s18-n02-t30
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Click-to-place sign, date and PIN fields for the selected signer with a keyboard alternative,
saved with the draft. Remaining part-2 items per DEC-1374.

## Plan
- Backend: `DraftUpdateIn.fields` (additive), `builder._replace_fields`.
- Frontend: SIG-02 Place fields toolbar, click-to-place, Remove; test.
- DEC-1374.

## Progress log
- `2026-10-30` — built; SIG-02 vitest (7), tsc, eslint run once; backend lint and types. `[skip ci]`.

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** P-04-T45 (staging E2E), then N-01-T27/T28.
