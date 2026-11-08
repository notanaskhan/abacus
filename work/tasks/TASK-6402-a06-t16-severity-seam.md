---
id: TASK-6402
title: A-06-T16 remainder - the deficiency severity suggestion target and its applier
spec: SPEC-000  # row
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: red
status: in-review
epic: A-06
plan_key: A-06-T16
branch: s26p-a06-t16-severity
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-08
updated: 2026-11-08
---

# TASK-6402 · A-06-T16: the agent's proposed severity as a suggestion a person adopts

TASK-3216 left the `deficiency_severity` suggestion target and applier out; `deficiencies.severity_suggestion_id` existed and nothing set it.

AC-1: An agent's `deficiency_severity` suggestion lands on a proposed deficiency as the agent's proposal, linked to the suggestion; a person's own proposal is never overwritten, and an unknown severity is ignored.

AC-2: Adopting it makes it the person's proposal in the adopting unit of work.

AC-3: Nothing here sets `severity_concluded`: concluding stays the engagement partner's decision (FINDING-001).

## Decisions (DEC-2952)
- Mirrors the checklist seam (DEC-2394): a `suggestion.created` subscriber and an applier, both in assurance.
- Assurance's subscription map holds one handler per event, and the checklist already held `suggestion.created`; one dispatcher now calls both seams, each ignoring the other's target.

## Known limits
- No producer creates `deficiency_severity` suggestions yet: the agent's fieldwork runs propose through `record_finding`. The seam is ready for the specialist that does (A-04 / A-05 runs, P-10).

## Progress log
- 2026-11-08: built on main a801fff01; tests written, run at the S26 partials end pass.
