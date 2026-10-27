---
id: TASK-1704
title: F-06-T24 ADR P-24 structured agent output (AgentBlocks)
spec: SPEC-400
acceptance_criteria: [AC-39]
risk_zone: red
status: done
epic: F-06
plan_key: F-06-T24
branch: s14-f06-t24
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Draft ADR P-24: a closed AgentBlocks schema, numbers by reference with the number-provenance check,
no model markup, citation offsets per segment, amending ADR-065; consumers F-06-T15, I-01, K-01-T21.

## Plan
Checklist (from 05 §5.4.5 and §5.3.10, AG-05, 09 P-24 and DEC-41, ADR-065, ADR-066, F-06 §5.2 and
§6, `docs/adr/backlog.md`), each item checked in ADR-230:
- [x] closed AgentBlocks schema, v1 parts as built (`agents/blocks.py`) plus v2 `h` and `ul` for T15
- [x] numbers by reference (`{fact}` segments) and the number-provenance check (one repair, then "Unsupported")
- [x] no model markup; renderers emit React nodes only
- [x] citation offsets per segment; "[n]" is never parsed from text
- [x] amends ADR-065 (what changes, what stands)
- [x] `proposal: P-24`, number ADR-230 from the S14 block, backlog and README rows
- [x] consumers F-06-T15, I-01, K-01-T21 named
- [x] two worked examples (a typed figure refused; a fact token rendered)
- [x] block list covers T15's DocBlocks (heading, paragraph segments, mini statement table, bullets)

## Progress log
- `2026-10-28` — ADR-230 drafted (status proposed), README and backlog rows; `validate_docs` clean on the branch.
- `2026-10-28` — ADR-230 accepted by ayushkbhatia (in chat); status, README index and backlog row updated.

## Questions for the human
- [x] Accept ADR-230: accepted by ayushkbhatia on 2026-10-28.

## Handoff
- **Current state:** accepted, PR open (stacked on F-06-T01 for SPEC-400), held for the S14 batch.
- **Exact next step:** the follow-up schema work (v2 `h`, `ul`, `total` rows) before F-06-T15.
