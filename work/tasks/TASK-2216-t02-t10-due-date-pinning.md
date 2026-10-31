---
id: TASK-2216
title: T-02-T10 due dates and BH-TAX-02 pinning
spec: SPEC-502
acceptance_criteria: [AC-18, AC-19, AC-20]
risk_zone: amber
status: done
epic: T-02
plan_key: T-02-T10
branch: s17-t02-t10
created: 2026-10-30
updated: 2026-11-01
---

## Objective
Original and extended due dates from K-02's `due_dates_for` on create and on extension change,
reference-set and BH-TAX-02 version ids pinned on the return, rule text for the Due popover,
recompute of unfiled returns on a published correction, the TPL-01 due-rule mapping test.

Acceptance (backlog row): "Ridgeline's extended 1065 resolves to Tue Sep 15, 2026 with its
version ids and a filed return keeps its pinned dates after a correction."

## Plan (amber)
- `tax/due_dates.py` (new): `FORM_FOR_RULES`, `pin`, `set_extended`, `recompute_unfiled`,
  `on_reference_set_published`, `rule_texts`; `tax/kind.py` pins on create; `tax/api.py`
  `SUBSCRIPTIONS`.
- `practice` (K-02-T07, stacked): `calendar.rule_text`, `DueDates.rule_text`,
  `extended_rule_text`.
- `methodology` (K-02-T08, stacked): `current_version_of_kind`.
- Audit action in the reviewed fallback list.
- No migration (0403 holds the columns), no matrix or flag change.
- Tests: `tests/unit/tax/test_t02t10_due_rules.py`, `tests/integration/test_t02t10_due_date_pinning.py`.
- Merge step: wire `rule_texts` into the board's `due_rule_code` when T-02-T09 lands.
- Rollback: revert.

## Acceptance
| Check | Test |
|---|---|
| Form mapping, rule text, period end, missing rules | `test_ac18_*` |
| Ridgeline extended 1065 Sep 15, 2026 with version ids | `test_ac19_*` |
| Filed keeps its dates after a correction; unfiled recomputed | `test_ac20_*` |

## Progress log
- 2026-10-30: built in S17 Lane 2 on K-02-T08; tests run in the end review.
- 2026-11-01: merged to main in #788 (ec9d5c58e).
