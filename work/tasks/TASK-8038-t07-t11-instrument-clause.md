---
id: TASK-8038
title: "T-07-T11: instrument_clause citation kind (evidence, red)"
spec: SPEC-656
acceptance_criteria: [AC-1, AC-6]
risk_zone: red
status: in-review
branch: t07-t11-instrument-clause
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: T-07-T11
---

## Objective
ADR-343's eleventh citation kind: the expand-only CHECK widening, registration through
`evidence.register_citable` with the clause verifier, regions for the lavender passage, moved on
a superseding instrument, and the C4 v1.2 note.

## Plan (red: written before the build)
1. Migration **0886** on 0885: drop and re-add `citations_kind_check` with `instrument_clause`.
2. **Protected** `evidence/citations/registry.py`: `CitationKind` and `SOURCES` gain the kind.
3. **Protected** evidence: `region_sources.py` (new slot, prefix `ic:`), `viewer.py` calls it;
   `api.py` exports `verify_document_citation`, `register_region_source`, `RegionHit`.
4. `tax/instrument_citations.py`: verifier, display, region source, `move_clause_citations`;
   registered from `tax/api.py`.
5. `docs/contracts/c04-citations-viewer.md` v1.2; T-07-T06's deferred consumer assertion joined.
6. Tests: `tests/unit/tax/test_t07t11_instrument_clause.py`.
Rollback: downgrade 0886 (refused while clause citations exist, by design); revert the code.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010); plan above written before building.
- `2026-11-15` — Built as planned (DEC-5024). Not run (end pass: migrations, unit, contracts,
  the citation eval suite, security review of the red diff).
- **Partial.** The database path (a seeded instrument with a word layer, the regions read and a
  real supersession) runs once T-07-T12's instrument service writes instruments, segmentations
  and clauses; T-07-T12 calls `move_clause_citations`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5024 | Reuse the document_text verifier; one region per quote; region-source slot; owner-driven moves | no (ADR-343) |
