---
id: TASK-2610
title: A-03-T09 sampler golden fixtures and frozen corpus
spec: SPEC-580
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: amber
status: in-review
epic: A-03
plan_key: A-03-T09
branch: s21-a03-t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-31
updated: 2026-10-31
---

## Objective
"The golden suite passes against T04 on both supported Python minors and fails if any selection
line in version 2.3 changes." (ADR-078 separate author: transcribed from the design, not T04.)

- **[AC-1]** Seed 0x5E2A91 on Northwind census v2 (412): the 25 designed names in order.
- **[AC-2]** Seed 0x7C31B4 on Granite Peak's 1,912 disbursements: strata 24 / 1,102 / 786, 24 + 16 =
  40 items totalling 3,698,700 (3,286,400 + 412,300), value share 9.6%.
- **[AC-3]** Size 22; UDL 8.8% and 19.9%; projection 35,267.20 with QA-3 recorded (DEC-1659).

## Scope
**In**: `backend/tests/golden/sampling/` (three YAML goldens with `source` and `reviewed_by`, the
test module with the two inverse-construction generators), `corpus/v2.3.yaml` (protected, red:
seven entries), a CI job running the folder on Python 3.12 and 3.13.
**Out**: the CPA's golden review (`docs/quality/golden-reviews/sampling@2.3.md`, human, before the
Tue Sep 21 flip); the scenario loader's Brightwater content (A-03-T13).

## Plan
1. [x] Transcribe AUD-11a card 3 (names, census IDs), SHT-01 c rows SURL-01 to 40 (vendors,
   payment dates, amounts) and the F1 statistics.
2. [x] Inverse construction (A-03 §5.4): census rows keyed "NWC-0001".."NWC-0412" in canonical
   order with the 25 designed participants at the ordinals v2.3 draws for 0x5E2A91 (recorded once
   as constants); GL rows keyed "GP-AP-00001".. with SURL-01 to 24 at ordinals 0-23 and SURL-25 to
   40 at stratum 2's drawn ordinals, fillers spread so each stays inside its stratum and the
   population foots to $38,640,200.00.
3. [x] Corpus: (seed, population_hash, version) -> items_hash for both goldens, the superseded
   seed 0x3C77D0, and four plain populations (1 of 1 at seed 0, 2 of 2 at the maximum seed, 30 of
   500, 60 of 64).
4. [x] CI `sampler-corpus` matrix (3.12, 3.13). Rollback: revert the PR.

## Progress log
- `2026-10-31` — 16 passed on Python 3.12.13 and 3.13.15. Lesson: a remainder-on-the-last filler
  spread pushed one stratum-2 filler over $50,000 (41 items); the spread now keeps the mean with
  paired +d/-d so every filler stays inside its band. The census row key is not the participant's
  census ID: the designed IDs' order cannot match the draw order (DEC-1659).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1659 | QA-3 settled for the golden; census and GL generator keys | No |
