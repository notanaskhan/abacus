---
id: TASK-7516
title: T-04-T52 independent AC tests for T23, T28, T36 and T39 (ADR-078)
plan_key: T-04-T52
spec: SPEC-649  # §3.4 (AC-4.1, AC-4.2, AC-4.7), §3.7 (AC-7.3 to AC-7.6), §3.8 (AC-8.x)
acceptance_criteria: [AC-4, AC-7, AC-8]  # AC-4.2, AC-7.6, AC-8.4: walled user sees no K-1 link; hand resolve of the dependency refused; every decision row names a human
risk_zone: amber
status: in-review
branch: t04-t52-services-ac
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
ADR-078's independent suite for the issues, scenario, K-1 and residency services: DEC-88 visibility
and walls, auto-resolve only by the system on release, override reason, residency confirmation
only by reviewer functions, human-sent client questions, CSV escaping, activity attribution.

## Plan
- `backend/tests/unit/tax/test_t04t52_independent.py`, from SPEC-649 and the rows' acceptance:
  `_source_visible` hides the K-1 link behind a wall or without read on the issuer; the Draft K-1
  issue is `system_resolved_only` and blocks final approval and export; a person's resolve or
  not-applicable answers 409 `system_resolved_only` with nothing written; an override's blank
  reason refuses before any read; `residency.confirm`, `k1_treatment.approve` and
  `k1_treatment.override` are reviewer functions and never the agent; a confirmation needs a named
  approver and a known option; the database's checks bind decisions to people; the client
  question is template words with no figure; `issue.send_to_client` is a person's; CSV cells are
  neutralised; the export is `export.create`, audited.
- Written in the solo session (DEC-1668 as amended).

## Progress log
- `2026-11-12` — Suite written (DEC-4516). It runs at the S39 end pass.
