---
id: TASK-362
title: Attribution and human-verb primitives — HumanAction, formatActor, AgentText restyle, AgentFilledMarker (F-05-T30)
spec: SPEC-048
acceptance_criteria: [AC-8]
risk_zone: amber
status: done
epic: F-05
plan_key: F-05-T30
branch: f05-t30-attribution
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"HumanAction refuses to render for an agent actor, formatActor yields 'X via Agent' and 'Policy:
name vN', and AgentText logic is unchanged."

## Plan (amber)
Files: `packages/ui/src/attribution/` (actor.ts, human-action.tsx, agent-filled.tsx, tests),
`agent-text.tsx` (classes only), specimens. No migration, flag or registry change. Rollback: revert
the commit; nothing reads the new exports yet except specimens.

## Scope
- `formatActor` (person, "X via Agent", "Policy: name vN", "Accrued Agent", "System") and
  `actorFromAudit` for the audit trail's `actor_kind`/`actor_name`.
- `HumanAction` for Approve, Sign off, Release, Send, Post, Decide, Adopt: renders only for a
  named person.
- `AgentText`: text-para ink-2, marked `data-actor="agent"`; sanitising unchanged (tested).
- `AgentFilledMarker` (C-31) with the six states, tooltip, Adopt as a HumanAction; `adoptSuggestion`
  and `editSuggestion` refuse a non-person.

## Definition of done
- [x] 13 tests in `attribution/attribution.test.tsx`
- [x] `make check-fast`
