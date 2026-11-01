---
id: TASK-2911
title: A-05-T14 EBP case sets in evals/workpapers_section_drafter
spec: SPEC-640
acceptance_criteria: [AC-12]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T14
branch: s24-a05-t14 (stacked on s24-a04-t14)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

EBP case sets for `ebp_provisions` and `ebp_attribute` in the one protected suite A-04-T14 created, with frozen thresholds.

## Acceptance (backlog)

The suite runs in CI on the fake route and its thresholds are frozen in suite.yaml before any EBP prompt merges.

## Plan

- `suite.yaml`: modes add `ebp_provisions`, `ebp_attribute`; threshold `line_agreement` 0.98 on those modes; cases: Northwind provisions (AA, amendment, SPD; labelled B3, B5, B14), a white-text instruction case, Northwind eligibility attribute (HR record; labelled C2).
- Graders: EBP modes share cell citation, number provenance, reserved actions and containment; methodology-step citation is at least one per section for EBP modes; `line_agreement` compares labelled values after normalising; validate needs a key case and labels per EBP mode.
- CLI `--mode` accepts the EBP modes; A-04-T14's test updated for the added mode and threshold.
- `evals/baselines.yaml`: `workpapers.section_drafter: {medium: "0.25"}`; `docs/product/failure-taxonomy.md`: an EBP section-draft defects list outside the screening tables.
- Test: `tests/unit/tools/test_a05t14_ebp_case_sets.py`.

## Progress log

- 2026-11-01: built in abacus-s24, stacked on A-04-T14. The fake answers were checked once against the graders while writing the cases; tests not run.
