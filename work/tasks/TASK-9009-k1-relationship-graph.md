---
id: TASK-9009
title: "T-06-T51: Tax relationship annotator and dependency chain"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-t06-t51-relationship-annotator
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: T-06-T51
---

## Objective
A user who cannot read the Feld engagement sees Ridgeline's graph without the Feld K-1 edge and without a count.

## Done
- organisations: K-1 flow provider slot with the viewer; graph read fixed to a session (ED-349); GET relationship-graph live (entities, parties, relationships, K-1 returns and edges, banner)
- tax/k1_relationships.py: flows from k1_packages and k1_handoffs with DEC-88 per viewer, code's banner, the release nudge
- tests: 2 (row acceptance on Postgres incl. the green banner after release; banner text)
- DEC-6015

## Progress log
- `2026-11-26` — Built; tests green. The viewer's saved positions are the graph-layouts row (not S54).
