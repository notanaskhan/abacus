---
id: TASK-8039
title: "T-07-T12: instrument service — attach, segment, clauses, determinations, review, lock"
spec: SPEC-656
acceptance_criteria: [AC-1, AC-3, AC-4, AC-5]
risk_zone: amber
status: in-review
branch: t07-t12-instrument-service
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: T-07-T12
---

## Objective
The instrument behind TXT-01: attach a client-level file to the 1041, code-only clause
segmentation, the instrument and clause reads, human record and edit of determinations with a
required clause citation and reason, `instrument_interpretation` as an L1/L3 reviewable, the L3
lock and reopen.

## Plan (amber)
1. `tax/instruments/segment.py` (pure) and `tax/instruments/service.py`.
2. `evidence/file_facts.py` + `evidence.api.version_file_facts` (file name, pages).
3. `fiduciary_contract.py`: the TXT-01 routes call the service (read, attach, clauses, mark,
   record, edit, reopen, cited-by); client regenerated.
4. `tax/api.py`: register the reviewable; `sign_off.recorded` runs the record projection and the
   L3 lock.
5. Tests: `tests/unit/tax/test_t07t12_instruments.py`.
Rollback: revert; the tables (0883) stay empty.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010).
- `2026-11-15` — Built (DEC-5025). A local run of the segmenter on a synthetic layer with the
  agreement's structure gives Art. I to V with III(a)/(b), IV(a)/(b) and V(c), III(a) over pages 3
  and 4, confidence 1.0. Not run otherwise (end pass).
- **Partial.** Cited-by is empty until T-07-T16; the reader block reads `agents_off` until
  T-07-T13; the trust profile's EIN joins with the entity's sealed TIN later (P-12 mask).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5025 | Segmentation grammar and bar; adopted on a person's change; L3 lock by consumer | no |
