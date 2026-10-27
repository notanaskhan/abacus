---
id: TASK-1705
title: T-02-T36 ADR P-68 tax computation boundary
spec: SPEC-401
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: T-02
plan_key: T-02-T36
branch: s14-t02-t36
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Draft ADR P-68 (DEC-77): the engine computes tax, credits and filed forms; Accrued shows engine
values only from approved imports and computes display arithmetic and workpaper figures in code;
draft K-1s never reach the portal (DEC-78).

## Plan
- Prerequisites: F-02-T02 done; F-02-T05 (ADR backlog) not listed as pending in the reconcile — ok.
- No T-02 spec exists yet (T-02 starts S16): SPEC-401 carries this one task's AC.
- ADR-231 from the S14 block; README index and backlog rows. No code, migration, flag or registry edit.
- Rollback: revert the branch.

## Per AC
| AC | Evidence |
|---|---|
| AC-1 | ADR-231 (proposed) records DEC-77 and DEC-78 and the computed/not-computed list; backlog row P-68 → ADR-231; `validate_docs` clean |

## Progress log
- `2026-10-28` — ADR-231, SPEC-401, README and backlog rows; `validate_docs` clean.

## Questions for the human
- [ ] Accept ADR-231 with the tax CPA by Fri May 28, 2027.

## Handoff
- **Current state:** drafted, PR open, held for the S14 batch.
- **Exact next step:** acceptance; T-02's S16 SPEC cites ADR-231 and supersedes SPEC-401.
