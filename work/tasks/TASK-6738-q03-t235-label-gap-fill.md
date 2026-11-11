---
id: TASK-6738
title: "Q-03-T235: label gap-fill through the platform labeler slot (tenant labelers, catalogue nouns)"
spec: SPEC-349
acceptance_criteria: [AC-6, AC-11]
risk_zone: amber
status: in-review
branch: s35b-q03-t235
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-11
updated: 2026-11-11
plan_key: Q-03-T235
---

## Objective
Unresolved target types show the catalogue noun, never an id or a Restricted value.

## Why the call-off applies
P-05-T11 (TASK-6703) found ADM-07 shipped without read-time value resolution for most target
types: only `user` has a labeler, and the label index calls labelers with no tenant
(`audit_labels(None, …)`), so a module that reads its own tables can't label anything for the
index. AUD-29 and ADM-07 rows showed identifiers.

## Plan
- `platform/audit_slots.py`:
  - **Tenant labelers:** `register_audit_tenant_labeler`, called with the viewer's firm or, for the index, the indexer's (`audit_labels(…, tenant=)`). With neither, nothing is named (fail closed).
  - **Nouns:** `audit_noun` and `register_audit_noun`. A type nobody names reads as its noun (`eqr_review` → "EQR review", `evidence_item` → "Document", or else the code in words). A noun carries no digits.
  - **TIN refusal:** a label carrying a TIN form is refused whatever its labeler declared (client content is hostile, ADR-052).
- `audit_trail/labels.py` (the index) and `audit_trail/explorer.py` (ADM-07, AUD-29): the
  index passes its tenant, and an unnamed target is its noun, never its id.
- Labelers, each in its owning module through `platform.api`:
  - `engagements/audit_labels.py`: `engagement` (its name) and `work_item` (its name, else the engagement's);
  - `organisations/audit_labels.py`: `client`;
  - `workpapers/audit_labels.py`: `workpaper` (code and title).
- Tests: `tests/unit/platform/test_q03t235_audit_labels.py`,
  `tests/integration/test_q03t235_audit_labels.py`.
- Rollback: revert; labels already indexed stay until the next backfill rewrites them.

## Partials (flagged)
- Labelers cover the four commonest targets. Every other type reads as its noun, which meets the
  row's acceptance; documents keep the noun on purpose, since a file's name is client content.
- The index rewrites older rows only on `backfill_labels`, run once per firm after deploy:
  `make backfill-rerun` (RB-46). This is a human step.

## Progress log
- `2026-11-11` — Built; unit tests pass (13), the integration test written (end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3304 | Tenant labelers on the slot, nouns for unnamed types, TIN-bearing labels refused | no |
