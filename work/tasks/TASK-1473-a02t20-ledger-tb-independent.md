---
id: TASK-1473
title: Independent AC tests for the ledger TB of record, layers and import hooks (A-02-T20)
spec: SPEC-333
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-6, AC-14, AC-17, AC-18, AC-19, AC-24, AC-25, AC-32]
risk_zone: red
status: in-progress
epic: A-02
plan_key: A-02-T20
branch: s12-ledger
created: 2026-10-27
updated: 2026-10-27
test_author: ayushkbhatia
test_session: 2026-10-27, s12-ledger (ADR-078 separate test session; did not write A-02-T07 or A-02-T22)
---

## Objective
"The suite fails when a snapshot is mutated, a layer is shown without its source, or a template
that does not foot is accepted, and passes on main."

## Plan
Tests only, written from SPEC-333 §5, the A-02 epic §3.1 to §3.8, C9 v1 (§2, §5 to §7),
`error-codes.yaml`, the assurance and workpapers matrix rows, `fresh-mfa-actions.yaml` and
DEC-316/DEC-610. No production code, migration, registry, flag or matrix edit.

- `backend/tests/integration/backfill/tb_support.py`: shared seeding (one firm, flags on, an
  audit engagement with its assurance item, a five-role team, three snapshots through
  `ledger.api.record_snapshot`; literals in the module docstring).
- `backend/tests/integration/backfill/test_a02t20_ledger_tb_independent.py`: adopt, human only
  (matrix and CHECK), immutability (UPDATE, DELETE, TRUNCATE for every role), entity mismatch,
  one TB per label, candidates and re-versioning (v1 and snapshots untouched, outbox event),
  prior pairing, per-layer balance, the fail-closed adjustment slot and an unbalanced source,
  leadsheet goldens and half-even rounding, Unassigned, Open in Excel (deterministic, fresh MFA,
  roles, agent, walls, formula text, audit hash), `ledger_line` verification, moved on re-version
  and never across engagements (security review fix, 2026-10-27).
- `backend/tests/integration/backfill/test_a02t20_tb_template_independent.py`: the template
  format (no "Accrued" in its words), refusals (does not foot, total row disagrees, wrong period,
  another system's file), and a footed template becoming an `import` snapshot.

Rollback: delete the three files.

## Progress log
- 2026-10-27: suite written (build first).
