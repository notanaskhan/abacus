# RW-1 · Tax return review workspace

| Field | Value |
|---|---|
| Version | v1 |
| Status | stub (T-04-T05, 2026-11-09, DEC-3020): every route answers 501 under its one action |
| Provider epic | T-04 (SPEC-649) |
| Consumers | TAX-04, TAX-05, TAX-06, TAX-07, TAX-08 screens (T-04 FE rows); T-05 (entity returns, read-only) |
| Flag | `tax.review_workspace` (T-04-T09) |
| Code | `backend/src/abacus/modules/tax/workspace_contract.py` |

## Who may call it
| Operation | Method and path | Action |
|---|---|---|
| Workspace summary (tab counts at the viewer's level, K-1 chip, assistant availability) | `GET /v1/tax/returns/{id}/workspace` | `tax_return.read` |
| Review tree | `GET /v1/tax/returns/{id}/review-tree?level=&q=&category=` | `tax_return.read` |
| Approve a document at a level | `POST /v1/tax/returns/{id}/document-approvals` | `document.approve` |
| Unapprove (a reversing row, own level) | `POST /v1/tax/document-approvals/{id}/reverse` | `document.approve` |
| Leadsheets | `GET /v1/tax/returns/{id}/leadsheets?form=` | `return_worksheet.read` |
| Sch E – K-1 matrix | `GET /v1/tax/returns/{id}/matrices/sch-e-k1` | `return_worksheet.read` |
| Region–field–line links | `GET /v1/tax/returns/{id}/links?evidence_version_id=` | `return_worksheet.read` |
| Request final approval | `POST /v1/tax/returns/{id}/final-approval-requests` | `tax_return.request_approval` |
| Start a draft run | `POST /v1/tax/returns/{id}/draft-runs` (202) | `tax_return.draft_run` |
Issues, checkpoints, proposals, sign-offs and field edits are P-04's routes (C3).
Client, agent and system principals hold none of the write actions (T-04-T03, DEC-3018).

## Status words
`document_approval` (Unapproved, Approved "✓ {count}", Mismatch), `k1_activity`,
`assistant_availability` (C2, T-04-T04).

## Human-only actions
`document.approve`, `tax_return.request_approval`, `tax_return.draft_run`; the final approval is
T-01's `tax_return.approve`.

## Errors
409 `mismatch` (`facts.field_key`), 403 `level_not_permitted`, 409 `version_superseded`, 409
`{blockers: draft_k1 | blocking_issues | unapproved_documents}`.

## Audit events
`document.approved`, `document.approval_reversed`, `tax_return.final_approval_requested`,
`tax_return.draft_run_started` (labels in T-04's ACTIVITY_KINDS with the build rows).
