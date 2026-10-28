---
id: TASK-1700
title: F-06-T01 screen contracts for the eight tier-3 boards
spec: SPEC-400
acceptance_criteria: [AC-33]
risk_zone: green
status: in-review
epic: F-06
plan_key: F-06-T01
branch: s14-f06-t01
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Screen contracts `docs/screens/<ID>.md` for T6, T10, T16, TPL-01, TPL-06, TPL-10, TPL-16 and TPL-19
with post-revision state tables (DF-03, DF-11, DF-12, DEC-45, DEC-97, DF-31 applied), verbatim copy
modules and the DECISIONS.md deviations. Also the epic's SPEC-400 (kickoff step 2).

## Plan
- SPEC-400 from the kickoff prompt: AC-1…AC-32 carry F-06.md §3 stories by number, AC-33…AC-39 the
  quality and hand-off rows.
- One contract per board from `docs/screens/_TEMPLATE.md`; every lettered artboard maps to a data
  condition, persona, clock, snapshot and parity tier; superseded states cite their DF/DEC row.
- Copy modules `apps/web/src/gallery/specimens/<ID>/copy.ts` (consumed by T04, T08, T10, T16).
- DECISIONS.md lines for Q4, Q6, Q7, the Issues label, the Ridgeline count (G-C02), the TPL-19 map
  and the native artboards. DEC-800 (TPL-19 letters), DEC-801 (tile order and the rest).

## Per AC
| AC | Evidence |
|---|---|
| AC-33 | the eight contracts; state coverage: T6 5, T10 5, T16 3, TPL-01 5, TPL-06 5, TPL-10 4, TPL-16 7, TPL-19 6 in scope + 4 deferred |

## Files
- New: `docs/specs/SPEC-400-f06-tier3-kits.md`, `docs/screens/{T6,T10,T16,TPL-01,TPL-06,TPL-10,TPL-16,TPL-19}.md`, `apps/web/src/gallery/specimens/*/copy.ts` (8), this file.
- Changed: `packages/ui/src/tokens/DECISIONS.md`, `docs/product/decision-log.md` (DEC-800, DEC-801).

## Progress log
- `2026-10-27` — Contracts, copy modules, SPEC-400 and decisions written. State coverage checked with a throwaway script. Tests, gates and review run once at the S14 batch end (Ayush, 2026-10-27).

## Handoff
- **Current state:** built, PR open, held for the S14 batch.
- **Exact next step:** batch-end gates (`make check-fast`).
- **Open issues:** Q1 and Q5 open until Fri Apr 30, 2027 (block T05/T06 only). DF-11 paper-form wording waits on counsel.
