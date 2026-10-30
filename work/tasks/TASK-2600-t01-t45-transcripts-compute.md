---
id: TASK-2600
title: T-01-T45 Transcript parser and comparison compute (tax/compute/transcripts.py)
spec: SPEC-501
acceptance_criteria: [AC-28, AC-29]
risk_zone: amber
status: in-review
epic: T-01
plan_key: T-01-T45
branch: s21-t01-t45
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Pure functions that parse IRS Wage & Income and Account transcript text and compare a Wage &
Income transcript with the return as filed, in exact decimals (ADR-050), for CLI-05 a.

Acceptance: "Goldens give 1,870.00 + 1,250.00 = 3,120.00 not on the return and four agreeing
forms for Whitley TY2024, with 100 percent line and branch coverage."

## Scope
**In**: `backend/src/abacus/modules/tax/compute/` (new package, `transcripts.py`); golden
transcripts and returns as filed in `backend/tests/golden/tax/transcripts/`; the golden suite and
the edge suite; SPEC-501 AC-28/29; DEC-1650; the tax README.
**Out**: storage, upload through the scanner, the routes and `TranscriptCompareWorkflow`
(T-01-T43); mapping the approved engine import's values to `FiledItem`s (T-01-T43); the screen
(T-01-T50); ADR-078 independent suite (T-01-T44).

## Plan
1. `tax/compute/transcripts.py`: `parse_amount`, `normalise_payer`, `payers_match`,
   `parse_transcript(text, kind)` → `ParsedTranscript` (information returns, transactions,
   balance, problems), `transactions_with_code`, `compare(parsed, filed, tax_year)` →
   `Comparison` (lines with status agrees / differs / not_on_return, difference total, agreeing
   counts by form, filed items not on the transcript, version). Hostile-text bounds (ADR-052).
2. Goldens: Whitley W&I and Account TY2024/TY2025 (synthetic text; designed figures only from
   CLI-05 a and blueprint §9), returns as filed in YAML with quoted amounts.
3. Tests: `tests/golden/tax/test_t01t45_transcripts_golden.py` (AC-29),
   `tests/unit/tax/test_t01t45_transcripts.py` (AC-28 edges, 100% line and branch).
Migrations, registry, flags: none. Zone: amber path `tax/compute/transcripts.py` (T-01 §4.1).
Rollback: revert the PR; nothing imports the library yet.

1. [x] Library. 2. [x] Goldens. 3. [x] Tests (run once: 32 passed, 100% line and branch).
4. [ ] End review.

## Progress log
- `2026-10-30` — Built on `s21-t01-t45`. The first comparison matched greedily, so an earlier
  line took a later line's exact pair; now exact-amount pairs go first (DEC-1650). Own tests run
  once (32 passed; `--cov-branch` 100% on `tax/compute`); pyright clean. Gates wait for the S21
  end review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1650 | transcript text grammar, compared field per form, matching order, refusal cases | no |

## Handoff
- **Current state:** built, PR open, held for the batch.
- **Exact next step:** end review; T-01-T43 stores transcripts and comparisons and maps the
  approved engine import to `FiledItem`s.
