---
id: TASK-1470
title: Evidence and import hooks — ledger_line verifier, Open in Excel, Accrued TB template (A-02-T22)
spec: SPEC-333
acceptance_criteria: [AC-6, AC-24, AC-25]
risk_zone: red
status: in-progress
epic: A-02
plan_key: A-02-T22
branch: s12-ledger
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"A ledger_line citation to a superseded snapshot verifies as moved, a re-render is
byte-identical, and a template that does not foot is refused unbalanced with its difference."

## Plan
- **`ledger_line` citable** (`evidence/citations/ledger_line.py`, registered from evidence;
  evidence → ledger is an existing edge, ledger stays dependency-free). Locator
  `{ledger_snapshot_id, account_code}` (extra fields refused). The verifier authorises
  `trial_balance.read` on the anchor's engagement before reading anything (no engagement, a wall,
  a role: `source_not_visible`); a snapshot of another entity than the engagement's is
  `source_not_found`, as if absent. Value checked against the line's net (debit − credit) or its
  printed side; the quote against the account name (case- and space-folded, contiguous). Match id
  `led:<snapshot>:<account>` (C4 §3.1); `source_version` is the snapshot id. Display: "Ledger
  line" · `<code> · <name>` only for a snapshot of the citation's engagement's entity.
  Ledger api gains `snapshot_line(session, snapshot_id, code)` and
  `superseded_snapshots(tenant, tb_id, version_no)` (reads only).
- **Moved**: evidence subscribes to `trial_balance.version_created` (`citations/ledger_moved.py`):
  when version n > 1 adopts a different snapshot, every live citation to version n−1's snapshot
  gets a `moved` event `ledger_snapshot:<new>` (idempotent on the cause, as P-03-T12).
- **Open in Excel** (`evidence/render.py` `render_trial_balance_layers`): one sheet per export,
  columns Account · Name · BOY · EOY (or the layer's AJE/RJE/Final columns) · Area · WP ref ·
  Ticks · Citations as text, a code-computed Total row, the balance, and a provenance footer
  (source, method, pulled, adopted by and when, version, snapshot id, layer). Stamped with the
  version's pull time, fixed ZIP entries: byte-identical on re-render; every client string
  written as text with the formula lead quoted (ADR-052). Route `GET …/export.xlsx` in
  `assurance/tb_read_model.py` (`trial_balance.export`, walls 404, flag 404 off), audited
  `trial_balance.exported` (activity catalogue entry).
- **Accrued TB template**: format `accrued_template` (xlsx; `Account` · `Account name` · `Debit` ·
  `Credit`; `Period end:` line; `Total` row) in `connections/import_formats.py`; source
  `import_accrued_template`. Migration **0235** (down 0220) re-adds `ledger_snapshots.source_kind`
  with the new source as `import`, refusing to run if any stored row would change kind (0149's
  rule). A template that does not foot fails `unbalanced` with its difference (existing check).
- Tests: `tests/unit/evidence/test_a02t22_ledger_line.py` (locator, value, match id, verifier
  refusals with fakes), `tests/unit/evidence/test_a02t22_tb_export_render.py` (byte-identical,
  formula neutralised, provenance footer), `tests/unit/connections/test_a02t22_accrued_template.py`
  (balanced parse, unbalanced with difference), `tests/integration/test_a02t22_ledger_hooks.py`
  (moved on re-version, export route audited, source_kind of the new source), migration up/down.
- Rollback: flag `ledger.tb_workpaper` off hides the export; downgrade 0235 restores 0149's
  expression (refuses while a template snapshot exists).

## Progress log
- 2026-10-27: plan written.
- 2026-10-27: built as planned (DEC-610). The C9 stub gate stays as `tb_contract.stub_gate`
  (no C9 stub left); the export route moved to `tb_read_model.py`. The template's client-visible
  words say "Trial balance template", never "Accrued" (DEC-01). Targeted tests and gates below.
- 2026-10-27: targeted pass green: unit and contract set 3,649 (incl. the new unit files), T22
  security file and T10 (16), ledger/portal/schema integration 198, schema-check subset 18, C9
  authz 2 (control updated: the export is live, so a missing TB answers 404), route introspection
  and fresh-MFA subset 87, tenant isolation subset 7. `test_tb_of_record_schema` expectation for
  `import_accrued_template` moved from `other` to `import` as its comment foresaw. Gates clean.
