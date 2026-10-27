---
id: TASK-1404
title: Retire portal.documents_v2 (R-01-T18 follow-up; DEC-443)
spec: SPEC-323
acceptance_criteria: [AC-3]
risk_zone: amber
status: in-review
epic: R-01
plan_key: R-01-T18
branch: s10-leftovers
created: 2026-10-27
updated: 2026-10-27
---

## Objective
R-01-T18 swapped `/documents` to POR-03/POR-04 and removed the legacy pages in #464, but left the
`portal.documents_v2` flag (DEC-443). Retire it so POR-03 and POR-04 are served to every firm.

## Plan
- Remove the flag from `docs/architecture/feature-flags/portal.yaml`; `make regenerate`
  (`_flags.py`, the generated client).
- Drop the gate from `portal/documents_routes.py` (three reads) and `requests/pbc_contract.py`
  (two undos); docstrings and `portal/pbc_contract.py` say so.
- Tests: the C5 stub test's documents flag-off case becomes `test_r01t18_portal_documents_v2_is_retired`;
  the undo contract cases, `test_portal_documents.py`, the scope-isolation support and suite and two
  backfill tests stop seeding the flag (they then prove the routes serve without it). No assertion
  on route behaviour is removed.
- Docs: `portal-pbc.md` flags row and route table, POR-03 flag-off row, DEC-510.
- Frontend: nothing reads the flag (checked with `git grep`).

## Rollback
Revert the commit (the flag returns default off; a firm without it sees POR-03's load error).

## Progress log
- 2026-10-27: built on s10-leftovers.
- 2026-10-27: targeted tests and gates clean; held in the s10-leftovers PR.
