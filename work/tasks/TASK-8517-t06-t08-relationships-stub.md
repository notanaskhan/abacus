---
id: TASK-8517
title: "T-06-T08: Relationships v1 contract stub (CLI-03)"
spec: SPEC-702
acceptance_criteria: [AC-34, AC-35]
risk_zone: red
status: in-review
branch: t06-t08-relationships-stub
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: T-06-T08
---

## Objective
Spec section: docs/plan/epics/T-06.md §4.3, §3 F8. Relationships v1 (organisations): graph and list projection with the annotation slot, create, update and end routes, external parties, per-user layouts; docs/contracts/relationships.md.

## Plan (red)
1. `organisations/relationships_contract.py`: graph read (its own route; P-07's live list unchanged), create, update, end, external parties, layouts; client 404, flag 404, human-only writes 403, then 501. P-07's ten relationship kinds; K-1 edges derived, never stored.
2. Fixtures `relationships_slice.py`: TPL-14 a (draft K-1s, amber), f (released, green), c (Calloway trust), e (single entity), and a walled view without the Feld household node or edge and no count.
3. `docs/contracts/relationships.md`; mounted; make generate.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5517). Ruff, pyright clean; generate clean. Gates and tests run once at the S49 end pass (build first, test last).
