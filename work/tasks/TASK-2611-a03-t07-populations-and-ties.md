---
id: TASK-2611
title: A-03-T07 populations and completeness ties in sampling
spec: SPEC-580
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4]
risk_zone: amber
status: in-review
epic: A-03
plan_key: A-03-T07
branch: s21-a03-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-31
updated: 2026-10-31
---

## Objective
"Census v2 yields 412 records and two ties, census v1 computes off $182,300.00, Granite Peak's
window yields 1,912 payments for $38,640,200, and an SSN column is refused with 422
restricted_column." (A-03 §3 F2 US-2.1 to US-2.3.)

## Scope
**In**: `sampling/populations.py` (pure builders and the service), `sampling/population_repository.py`,
the three population routes live (create, read for non-fixture ids, ties), `evidence.api` exports
`extract_isolated`, `Extraction`, `ExtractedTable`, `masked_rows` and the new
`evidence.pii.column_families` (red files: one pure function and re-exports), error codes,
contract doc §5, regenerated client.
**Out**: draws, versions and approval (`completeness_tie_required`, `population_not_tied`) are
A-03-T10; the outbox `population.created` event waits for its first consumer (T10/T13); the upload's
file name, version number and uploader on `PopulationOut.source` (evidence exposes no read of them
by version for another module yet: T11's live swap adds one or reads the evidence drawer); the GL
path's Postgres test (a GL snapshot needs a TB snapshot chain; the pure path is unit-tested).

## Plan
1. [x] Pure: column map by header or letter; Restricted by the masking's own rules (header families,
   or any value it would mask); cells kept as text; money parsing; canonical rows, SHA-256, total;
   GL lines by accounts, side, kinds and window; ties by code; the two GL ties.
2. [x] Service: upload (version on the engagement, `read_version` authorises and audits, isolated
   parse), GL (snapshot of the engagement's entity, paged `gl_entries`), one unit of work with
   `population.created` and `population.tie_recorded`; ties authorise `population.create` on the
   population's engagement, citations must be `supported_citations` (INV-2), an advisory lock
   serialises positions (DEC-1656's lesson).
3. [x] Routes: create (work item's engagement; non-person refused), read (fixtures first, then
   live on the population's engagement), ties. Rollback: revert (no migration).

## Progress log
- `2026-10-31` — Unit 21 passed; HTTP integration 6 passed (412 records and two ties, off
  182,300.00, 422 restricted_column, 422 citation_unverified, another engagement's evidence 404, a
  stranger refused). Lesson: `errors=` lists only optional statuses (409, 410, …); 422 is always
  documented. A module the routes import lazily must still be imported by `api.py`, or its error
  classes miss the catalogue.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1660 | Population sources, Restricted columns, ties and gates as built | No |
