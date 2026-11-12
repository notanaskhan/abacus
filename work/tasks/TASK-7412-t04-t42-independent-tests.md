---
id: TASK-7412
title: "T-04-T42: Independent AC tests (ADR-078) for T14, T19 and T30: tax_form_line verification, tool consent refusal, offshore masking, scope pinning, propose-only tools, export only from an approved checkpoint, imports pending until approved, never-transmit"
spec: SPEC-649
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: s38-t04-t42
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T42
---

## Objective
Each property fails when its guard is removed, and no tool or export path returns a full TIN or
changes a value without a human approval.

## Plan (red, tests only)
`backend/tests/unit/tax/test_t04t42_independent.py` (19 pass), from SPEC-649 and the rows'
acceptance, each test naming its guard:
- T19: kinds of the registered tax tools; every read and compute tool is `tri` (the runtime's
  consent gate before the handler); every propose tool's output is the proposal's identifiers
  only, action `proposal.create`; no output field can hold a full TIN; a targeted tool pins the
  run's engagement and the named taxpayer, extra fields refused; the scrub leaves no full SSN or
  EIN (property test).
- T14: printed amounts as numbers (a fabricated figure never equals), the linked-figure label,
  a box cited by page and bbox for the word-layer re-read.
- T30: the export carries Accrued fields and never an engine-computed line, an unmapped engine key
  refuses, a one-dollar difference raises one tie-out and equal figures none, no e-file channel in
  the export path or the tools (NEVER-ERO-001).

## Partial
- The database-backed halves (consent refusal with one spouse signed, export only from the
  current approved checkpoint, an import pending until its checkpoint is approved, the moved state
  on a superseding upload) stay with T-04-T14/T19/T30's integration suites, run at the end pass.

## Progress log
- `2026-11-12` — Written (S38). 19 pass; lint and types clean.
