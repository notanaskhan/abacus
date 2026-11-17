---
id: TASK-8442
title: "C-01-T36: rest: CLS-09 AJE POLICY card, template tag and version stepper"
spec: SPEC-655
acceptance_criteria: [AC-22]
risk_zone: green
status: in-review
branch: s48r-cls09-gaps
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T36
---

## Objective
CLS-09 drew neither the AJE POLICY tally card nor the template Tag (no contract fields) and the version stepper had no behaviour. PlanVersionOut now carries template_name and aje_policy, and the stepper reads any version.

## Plan (green)
1. closes.plans: template_name from close_plans.template_key (newest close_templates version) and aje_policy as the one threshold policy the rows cite, named by methodology.api.threshold_policy_labels ("BH AJE thresholds v2").
2. CLS-09: Tag "Template · {name}", the AJE policy tally card, the ⇕ Menu of versions (history) that sets ?version.
3. Fixture, test and the screen contract's DV-a and DV-d.

## Progress log
- `2026-11-17` — Built (S48 rest, DEC-5430). Not built: "+ Add procedure" (no add-row artboard; inventing the form would break the verbatim-copy rule) and the ENG-03 monthly-close step (needs the engagement draft's close-template field and closes generated on create, across engagements and closes): both left for a follow-up. Gates and tests run once at the S48 end pass (build first, test last).
