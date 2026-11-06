---
id: TASK-5018
title: A-05-T16 remainder - EBP-03 reads the entry rule from the verified provision
spec: SPEC-640
acceptance_criteria: [AC-14]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T16
branch: s25c-a05-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s25c
created: 2026-11-06
updated: 2026-11-06
---

# TASK-5018 · A-05-T16: EBP-03 reads the verified entry rule

TASK-3022 published `verified_provisions`, but nothing read it. EBP-03's sample and the census-to-HR
check called the eligibility engine with Northwind's defaults, whatever the plan said.

## Objective
The row's own words: "EBP-03 reads the entry rule from the verified provision, never from the draft."

## Plan (amber)
- `compute/ebp/eligibility.py`: `EntryRule`, `entry_rule_from` (reads the verified wording, or None),
  `entry` and `review` compute from the rule they are given; `Entry.service_on`.
- `ebp_provisions.py`: `entry_rule_of`, `entry_rule_read` (no paper or no review is unverified).
- `ebp_eligibility_sample.py`, `ebp_attribute.py`: read it; with no rule, open no date of birth and
  compute nothing.
- `ebp_contract.py`: `EligibilitySampleOut.entry_rule` (`EntryRuleOut`); client regenerated.
- EBP-03: the amber notice, the computation line from the rule, scenario f.
- No migration. Rollback: revert.

## Acceptance
| Check | Test |
|---|---|
| Wording read, or left for a person | `tests/unit/assurance/test_a05t16_entry_rule.py` |
| A drafted provision never reaches the rule | `test_ac_a_drafted_provision_never_reaches_the_rule` |
| Unverified: nothing computed, no birth date opened | `trust_kit/test_a05t23_eligibility_sample.py::test_ac_an_unverified_entry_rule_*` |
| The verified rule moves the date | `test_ac_the_verified_rule_moves_the_entry_date` |
| The screen's notice and no dates | `EBP-03.test.tsx` f |

## What stays open on the row
The SPD conflict pill and amendment tag on EBP-02's read model stay null: they need SPD values a
person enters, and nothing stores those yet (DEC-2069). EBP-04's match formula and EBP-09's expenses
clause do not read `verified_provisions` yet, and EBP-03's escalation rate and missed amounts still
use the engine's QACA constants. So the row stays `partial`.

## Decisions made during this task
DEC-2482.

## Progress log
- 2026-11-06: built; targeted tests and check-fast passed on the first commit. Security self-review findings then fixed: the attribute guard opens the date of birth with or without a rule, wordings with symbols count as unreadable, a row with no hire date opens nothing. Tests for these are written but not yet run: the owner held this session's tests so other sessions get the CPU. Run them before the PR.
- 2026-11-07: Merged main, which took this row's first number while it was held; other sessions then held the next ones, so it moves to a block clear of them. End test pass on the merged branch: targeted backend tests 66 passed, EBP-03 web tests 14 passed, tsc, eslint and check-fast. One comment line shortened.
