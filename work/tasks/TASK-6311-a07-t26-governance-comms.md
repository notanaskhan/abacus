---
id: TASK-6311
title: A-07-T26 governance communications service (AUD-22)
spec: SPEC-644  # A-07 F4
acceptance_criteria: [AC-1]
risk_zone: amber
status: partial
epic: A-07
plan_key: A-07-T26
branch: s32-a07-t26
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
AUD-22's service: four kinds, sections from facts, regenerate merge, approval, EP approve-and-send
to the POR-15 room or an acknowledgement envelope, AU-C 265 due date, output checks.

## Plan
- New `assurance/governance_comms.py`; AUD-22 routes in `assurance/release_contract.py` live
  (list, create, read, compose/regenerate, edit section, request approval, approve-and-send,
  recipients get/put).
- Sections sealed with R-02-T12's fingerprint so the room reads them; acknowledgement is R-02-T12's.
- Tests: `tests/unit/assurance/test_a07t26_governance_comms.py`.
- No migration (0668, 0710).

## Progress log
- `2026-11-09` — Built; ruff, pyright clean; tests written, not run (end pass). Partial: the
  `ack_envelope` channel records the send but does not draft the SIG-02 envelope (C7, with
  A-07-T33's letters flag); recipients' `tcwg` grants and invitations are not yet issued at send
  (the room reads existing grants); section wording is code over facts, the firm's C11 governance
  templates (A-07-T12) are not yet merged into the composition; the AUD-22 stub tests asserting
  501 need evolving at the end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3011 | Section keys per kind, merge rule, output checks, 703 inside 265, due rule | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status partial.
- `2026-11-09` — Partials round (branch s32p-a07-t26-grants, DEC-3026): approve & send issues
  each recipient's `tcwg` grant on the room, or a pending grant and invitation; unit tests in
  `tests/unit/identity/test_a07t26_tcwg_grant.py`.
- `2026-11-09` — Partials round (branch s32p-a07-t26-templates, DEC-3027): create takes an
  optional published `governance_letter` version; its paragraphs open the letter, versions store
  the template and regenerate keeps it; contract field added (client regenerates at the end
  pass); unit test. Still open: the SIG-02 envelope draft for `ack_envelope` (A-07-T33).
