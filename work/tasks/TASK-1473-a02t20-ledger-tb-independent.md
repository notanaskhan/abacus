---
id: TASK-1473
title: Independent AC tests for the ledger TB of record, layers and import hooks (A-02-T20)
spec: SPEC-333
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-6, AC-14, AC-17, AC-18, AC-19, AC-24, AC-25, AC-32]
risk_zone: red
status: done
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

## Results (per AC)
- AC-1, AC-2, AC-3: `test_ac1_*`, `test_ac2_*` (matrix, CHECK, UPDATE/DELETE/TRUNCATE for every role
  on snapshots, lines and versions), `test_ac3_*`: pass.
- AC-4 (versions, prior pairing, outbox `trial_balance.version_created`): pass.
- AC-14, AC-17 (fail-closed slot, `layer_unbalanced` with its difference, a balanced AJE moves
  Final): pass. AC-18, AC-19 goldens (Investments 13,940,000 · 16,500,000 · 2,560,000 · 18.4;
  KRS 500 Index 20.0; half-even 0.0; Unassigned): pass.
- AC-24, AC-25 (deterministic export, audit hash, fresh MFA, roles, agent, walls, formula text):
  pass. AC-6 `ledger_line` (verify, mismatch, extra field, other entity, moved, never across
  engagements per DEC-613 M): pass.
- Template (`test_a02t20_tb_template_independent.py`): 6 pass, 1 strict xfail.

## Strict xfail
- `test_ac24_a_total_row_labelled_in_the_account_column_is_still_the_control`: a template Total
  row labelled in the Account column is dropped instead of read as the control total, so a file
  whose Total disagrees with its lines is accepted (`totals_from_lines: true`). With the label in
  the Account name column it is refused. **Needs an ED number** (ED-175 to ED-177 went to
  TASK-1474's findings); the template's documented layout does not say which column holds the
  label, so the main session may instead decide it is a spec gap.

## Spec drift
Recorded in DEC-551: error-codes.yaml statuses over C9 §6 (`snapshot_entity_mismatch` 422);
candidates are the entity's snapshots (SPEC-309); the app registers fieldwork's adjustment
source, so the fail-closed slot is tested by emptying it; a template's format id
`accrued_template` is internal, only its system and steps are client words.

## Progress log
- 2026-10-27: targeted pass, foreground, -n 2: ledger file 50 passed; template file (one process,
  Temporal workers) 6 passed, 1 xfailed. Gates below.
