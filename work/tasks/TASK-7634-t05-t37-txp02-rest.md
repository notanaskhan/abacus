---
id: TASK-7634
title: T-05-T37 rest — TXP-02 overlays (a2, a3, e2) and the three statement ties
plan_key: T-05-T37
spec: SPEC-651
acceptance_criteria: [AC-F3]  # SPEC-651 AC-3.1 to AC-3.4: ties, the entry drawer, cell provenance, the line picker
risk_zone: amber
status: in-review
branch: t05-t37-txp02-rest
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Finish TXP-02, partial in TASK-7627: SHL-09 on an amount's workbook cell (a2), the entry drawer
(a3), the line picker and its mapping (e2), and the handoff's nine tally cards with server
derivations.

## Plan (amber: a ledger mapping write, human only)
- `tax/entity_tb.py`: `capital_roll`, `statement_tallies` (balance sheet, capital tie against M-2
  line 9, retained earnings against M-2 line 3; `pending` before sheet 07), `TbTerm` derivations
  on tallies and figures, `account_cells` / `with_cells` (sheet 01 addresses), entries returned
  whole (`adjustments.api.Entry`, re-exported).
- `tax/entity_mapping.py`: `form_line_choices` (published mappable lines, search) and
  `pick_form_line` (DEC-4629: the tax reviewer maps through C9's `record_form_line`, audited
  `tax.mapping_recorded`; anyone else raises a review note; unknown key 422 first).
- `tax/workbook_contract.py`: `/form-lines` and `…/mappings` served; additive `cells`, `terms`,
  entry `description` / `lines` / `approval`; `WorkbookMappingProposedOut` reshaped (stub, no
  consumer). `audit_trail/activity_reviewed.py`: `tax.mapping_recorded`.
- Tests: `tests/unit/tax/test_t05t37_txp02_rest.py` (goldens), `test_t05t37_line_picker.py`.
- Web: `screens/TXP-02/{index,Financials,Overlays,copy,TXP02.test}`, kit `TallyStrip` `info`
  on tally cards, fixtures (cells, ties, terms, entries, form lines, mapping, provenance).
- Rollback: revert; the routes go back to 501 and the screen to six cards.

## Partial
- The entry drawer's source citation (SHL-08) needs `proposed_entries.source_ref` in C8's read
  (A-06, red); the drawer shows lines, memo and the named approval.
- Artboards a2, a3 and e2 open their overlays on interaction, not on load.
- The footnote's PY clause is the handoff's TY2024 text, shown once PY is imported.

## Progress log
- `2026-11-13` — Built (DEC-4629). The audit `Ref` first carried the account code and key; the
  kernel takes IDs only (caught by the unit test); it names the mapping set.
