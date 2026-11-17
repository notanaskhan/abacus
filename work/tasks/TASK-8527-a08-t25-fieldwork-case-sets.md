---
id: TASK-8527
title: "A-08-T25: Fieldwork case sets in the section-drafter suite"
spec: SPEC-657
acceptance_criteria: [AC-9]
risk_zone: red
status: in-review
branch: a08-t25-fieldwork-evals
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T25
---

## Objective
Add the three fieldwork modes (fieldwork_attribute, flux_explain, confirmation_reconcile) to the one suite evals/workpapers_section_drafter/suite.yaml with Granite Peak and Lakeshore cases, adversarial respondent attachments, graders and frozen thresholds; failure-taxonomy rows; cost baseline. AC: fake-route suite green at citation 1.0, extraction 0.98, abstention 0.95, containment 1.0.

## Plan (red)
1. section_drafting.py: FIELDWORK_MODES, ABSTAIN_MODES, Mode literal, labels abstain/explain, metrics abstention (>=0.95) and extraction (>=0.98, gated apart so line_agreement's EBP rate is not pooled), fieldwork reserved results (passed, no effect, exception raised, accepted)
2. suite.yaml: 11 fieldwork cases from the fieldwork seed figures (Granite Peak invoices, 14 flux lines, Summit Trail confirmation 412,600.00 / 4,300.00; Lakeshore grants), three adversarial
3. __main__.py --mode choices from the Mode literal
4. failure-taxonomy rows; baselines small tier 0.05
5. tests/unit/evals/test_a08t25_fieldwork_case_sets.py; A-04-T14 pinned sets extended

## Progress log
- `2026-11-17` — Built; fake-route suite passes per mode and in full; section-drafter eval unit tests pass (31). Classification agreement gated at the stricter 0.98 with extraction. Bedrock report and the driver-attribution judge wait on A-08's real-route run (no key, no staging). Gates and tests run once at the S49 end pass (build first, test last).
