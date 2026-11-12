# RW-1 · Tax return review workspace

| Field | Value |
|---|---|
| Version | v1 |
| Status | **final (T-04-T50, S39, 2026-11-12; DEC-4528)**: every route is served. Built in S33–S39: workspace, review tree, approvals and Undo, final-approval request (T-04-T17, T-04-T29), leadsheets, Sch E – K-1 matrix and links (TASK-7330), K-1 activities and treatments and their runs (T-04-T36, T-04-T38), residency and state allocation (T-04-T39), the draft-run entry (T-04-T55: a person only, 409 `draft_not_allowed` from final approval on). The return frame lists its tabs from `tax.return_tabs` (T-04-T55). Additive changes only from here; a breaking change is v2 |
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

## Leadsheets, the matrix and links (TASK-7330, DEC-4330)
- `GET …/leadsheets?form=1040`: one card per section of the form's active worksheets; one line per
  `line_ref` as `{form}.{line_ref}`, the amount summed in code, the contributing field keys, and
  `mismatch` when a box a field cites printed another figure.
- `GET …/matrices/sch-e-k1`: per K-1 activity, its worksheet's amount lines with the prior-year
  K-1's figure for the same field key (`prior_year` is null for a viewer who may not read last
  year's engagement, or when last year had no such line); `tax_year` and `prior_year` from the
  return.
- `GET …/links?evidence_version_id=`: each field's latest version's verified `document_text`
  citations with a page and a box: `match_id`, the evidence version, the page, the box, the field
  and its line. A withdrawn, moved or shadow citation is never a link (INV-2).
- The code mismatch check (SPEC-649 AC-1.4): a document a box of which printed a figure other than
  the field citing it reads `approval: "mismatch"` in the review tree with `mismatch_field_key`;
  `POST …/document-approvals` on it answers 409 `mismatch` with `facts.field_key` and writes
  nothing. An approval made before the mismatch stays approved.


## Close-out (T-04-T50, S39; DEC-4528)
- **Consumers.** T-05 (entity returns) registers its frame tabs with `register_return_tab` and
  reuses the review grammar (C3) and TAX-08's assistant; T-06 (fiduciary and states) adds its
  worksheets through `tax-worksheets.md`'s form registry; T-07 (planning) reads approved fields
  only through `review.api.values_as_of`; T-08 (filing) reads the final-approval checkpoint and
  `allowed_actions`, never the workspace's tables; W-02 (Workbench) opens TAX-08's session by
  `return_id`.
- **Adding a return tab:** `tax.api.register_return_tab(tab, flag, order=, forms=)` at import; the
  frame lists it only while the flag is on (DEC-4514), and the tab's route answers 404 otherwise.
- **Gates:** the CPA memo `tax-individual@v1` (T-04-T49), the mutation scope `tax/individual` and
  the p95 budgets (T-04-T53), the flip runbook `tax-workspace-flip.md` (T-04-T54).
