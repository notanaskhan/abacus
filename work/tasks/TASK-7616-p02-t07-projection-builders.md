---
id: TASK-7616
title: P-02-T07 projection builders for client, tax_return, assurance, binder, document, inbox_thread, todo
plan_key: P-02-T07
spec: SPEC-000  # C15 v1, docs/contracts/c15-search.md; ADR-241
acceptance_criteria: [AC-1]  # the seven types index the E0 seed (feld, granite, ridgeline) and no row holds a TIN, amount or document text
risk_zone: red
status: in-review
branch: p02-t07-projections
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Each owning module registers its C15 v1 projection (builder, lister, triggers) so the indexer can
build metadata-only rows, with a code-only PII and bidi scrub of hostile names.

## Plan
- `organisations/search.py` `client` (Clients; CLI-02; name, practice-management ref, entity
  names; context descriptor · office; trigger `client.updated`).
- `tax/search.py` `tax_return` (Returns; `tri`; title "<year> Form <form>"; K-1 recipients as
  related parties "Jonah Feld, limited partner 25%"; entity returns → CLI-02 while TXP-01 is
  planned, `ENTITY_RETURNS_TO_TXP01`; triggers `tax_return.approved`, `.ready_to_transmit`,
  `k1_package.released`).
- `engagements/search.py` `assurance` (Audits; AUD-02; phase as status; `assurance.phase_changed`).
- `requests/search.py` `binder` (Binders; BND-02; "n requests open" by code; request item events).
- `evidence/search.py` `document` (Files; FIL-01 on its folder; withdrawn items answer None;
  `evidence_version.created`, `.withdrawn`). `EvidenceVersionWithdrawn` gains `evidence_item_id`
  (additive) so a withdrawal drops the row at once.
- `communications/search.py` `inbox_thread` (Inbox; INB-01; matched threads only; subject
  scrubbed; sender a related party; `inbox_attachment.received`).
- `collaboration/search.py` `todo` (To-dos; SHL-17; open, on an engagement; assignee and due date;
  every `todo.*` event).
- `platform/search/scrub.py`: TIN shapes, nine-plus digit runs and currency or grouped amounts →
  `•••`, after the control and bidi pass.
- Each module's `api.py` imports its `search.py` (registration at import).
- Test `backend/tests/unit/platform/test_p02t07_projections.py`.
- Rollback: revert; the rows stay unread until P-02-T08.

## Deviations (DEC-4613)
- The `assurance` projection lives in `engagements` (it reads `work_items` and
  `assurance_work_items`, engagements' tables), not in `assurance`.
- Inbox rows open INB-01 (INB-02 is planned); entity returns open CLI-02 until TXP-01 is built.
- Client names in binder, document and to-do rows are not in the context: requests, evidence and
  collaboration may not import organisations; the client's own row carries the name.
- No `client.created` event exists: a new client is indexed by the reindex CLI (or the next
  `client.updated`). P-02-T08's query re-filters by `visible()` at read, so a stale row never leaks.

## Partial
- The E0-seed footing (feld, granite, ridgeline return the designed rows) runs at the end pass with
  P-02-T09's suite against a seeded database.

## Progress log
- `2026-11-12` — Seven projections and the PII scrub built (DEC-4613).
