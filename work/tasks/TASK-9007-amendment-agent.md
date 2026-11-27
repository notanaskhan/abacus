---
id: TASK-9007
title: "T-08-T34: Amendment drafter mode and the bba_route recommender"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s54-t08-t34-amendment-agent
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: T-08-T34
---

## Objective
The amendment proposal and the push-out recommendation are suggestions with verified citations, and neither can record an election or touch the original.

## Done
- tax/amendment_agent.py: draft_amendment (Part II suggestion + agent version + proposed checkpoint of code's changed lines, verified citations, C19 first, synthetic only) and recommend_bba_route (checked recommendation as a suggestion tagging the signer's card)
- practice_modes ModeInput gains amendment; recommender_modes gains bba_route; recommendation_facts.bba_route_facts
- prompts tax.return_drafter.amendment@v1 and decisions.recommend.bba_route@v1; drafter spec scope suggestion.create (specs regenerated)
- routes: amendments/{id}/proposals:draft and aars/{id}/recommendation:draft live
- tests: 10 unit (facts, settling, refusals, recommendation checks, no election or original write, spec scopes); agents and gateway unit suites 1,546 passed
- DEC-6013

## Progress log
- `2026-11-26` — Built; fake-model only. Human: Bedrock runs for both modes (DEC-6001); eval cases are T-08-T29.
