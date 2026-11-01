---
id: TASK-2914
title: A-06-T02 status vocabulary and glossary rows (DF-31, DF-28)
spec: SPEC-642
acceptance_criteria: [SPEC-642 AC-4]
risk_zone: red
status: in-review
epic: A-06
plan_key: A-06-T02
branch: s24-a06-t02 (stacked on s24-a06-t01)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

The status words A-06's records use, with pill variants, in the one vocabulary, and the glossary terms.

## Plan

- `status-vocabulary.yaml`: `misstatement` gains Passed on SUM; `proposed_entry` gains Client declined and Rejected (DF-28); new groups `finding_route`, `statement_document`, `fs_approval`, `disclosure_answer`, `consultation`. `deficiency`, `deficiency_severity` and `review_note` already carry A-06's words (Reopened is an event, not a state).
- Regenerated `kernel/_statuses.py` and `packages/ui/src/status.gen.ts` (`python -m abacus_tools.codegen.status_vocabulary`).
- Glossary: the A-06 table names (DEC-1960), Passed on SUM, SUM, Consultation.

## Progress log

- 2026-11-01: built in abacus-s24, stacked on A-06-T01.
