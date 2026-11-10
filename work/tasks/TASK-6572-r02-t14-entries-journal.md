---
id: TASK-6572
title: "R-02-T14 remainder: POR-08's Download entries as C11's client_entries_journal"
spec: SPEC-646  # R-02 §5 journal route; DEC-44 deterministic journal
acceptance_criteria: [AC-1]  # the row's acceptance (Objective)
risk_zone: red
status: in-review
branch: s33t-r02-t14-journal
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-10
updated: 2026-11-10
plan_key: R-02-T14
---

## Objective
`GET /portal/approvals/{kind}/{item_id}/journal` answers 202 `{render_job_id}` while C11 renders a
deterministic entries journal, then 302 to its bytes; two renders of one item are identical.

## Plan (red)
- Migration 0763 (on 0762): the `generated_documents.kind` and `report_templates.family` CHECKs
  widen by `client_entries_journal` (0745's pattern; expand only).
- `reporting/entries_journal.py`: the kind, composed by code in the `financial_statements` layout
  from the C18 item's lines (Account · Debit · Credit, "$" with cents, "—" empty; POR-08 handoff);
  owner `client_approval_item`; `journal()` renders on first request in the person's name, serves
  a filed PDF again, renders a failed one again. Registered at import (`reporting/api.py`).
- `portal/approvals_contract.py`: the journal route (202 or 302) and `…/journal/file` (the PDF,
  `no-store`, attachment), each admitting the person exactly as POR-08's detail does
  (`service.approval`: live client human, sent item, covering grant). `portal/approvals.py`
  gains `item_scope`. Contract doc updated; `make generate`.
- Tests `tests/unit/reporting/test_s33t_r02t14_journal.py`.
Rollback: revert; downgrade 0763.

## Notes
- A sent C18 item is frozen while it waits, so the first filed journal is served again; a later
  change to the item would need a new render (the provider's `seen_hash` names it).
- Byte identity of two PDF renders can't be checked here (no WeasyPrint libraries locally); the
  composition is shown identical, and the renderer is deterministic (DEC-44).

## Progress log
- `2026-11-10` — Built; unit tests pass (8). Migration not applied locally. Gates at the end.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3172 | The journal is a composed C11 kind owned by the item; served from the API's own route | no |
