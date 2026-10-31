# K-1 packages (v1; C5 additive v1.x)

| Field | Value |
|---|---|
| Version | v1 |
| Status | T-02-T21 (2026-10-31): release and undo live behind `tax.k1_release` (T-02-T20's firm reads, share, release check, resend and details review before them); the portal routes (T26) stay 501 |
| Provider epic | T-02 |
| Consumers | TXP-12, POR-13, TAX-03 (hand-offs), R-02 (deliverables v0; the C10 precursor) |
| Spec | SPEC-502 AC-5; `docs/plan/epics/T-02.md` §3, §4.3 |

## 1. Routes
| Operation | Method and path | Action |
|---|---|---|
| TXP-12 rows · package · SHL-08 manifest | `GET /v1/tax-returns/{id}/k1-packages` · `GET /v1/k1-packages/{pid}` · `…/documents/{doc}` | `k1_package.read` |
| Share to another return's intake | `POST /v1/tax-returns/{id}/k1-packages:share-internal` | `k1_package.share_internal` |
| Release check · release (202, approval grant, `not_before` +10 s) · undo | `GET …/k1-packages/release-check` · `POST …/k1-packages:release` · `POST /v1/k1-releases/{rid}:undo` | `k1_package.read` · `k1_package.release` (fresh MFA; only `tax/k1_release.py`, K1RELEASE-001) |
| Resend | `POST /v1/k1-packages/{pid}:resend` | `k1_package.resend` |
| DV-10 review | `GET /v1/k1-recipients/{rid}/details-changes` · `POST /v1/recipient-details-changes/{id}:accept`, `:reject` | `k1_recipient.review_details` |
| POR-13 | `GET /v1/portal/k1s`, `/{pid}`, `/{pid}/download`, `/{pid}/attachments/{doc}` | `portal_k1.read`, `portal_k1.download` |
| Details change, e-furnishing consent | `POST /v1/portal/k1-recipients/{rid}/details-changes`, `POST /v1/portal/k1s/{pid}/e-furnishing-consent` | `portal_k1.update_details` |

A recipient sees only their own packages, released and later (service; the MFA floor is the portal session's). Drafts never reach the portal.

## 2. Status words
`k1_package` (blueprint; client words "Not released yet"), `recipient_details_change`, `k1_handoff`.

## 3. Classification
Box amounts TRI; names and addresses confidential; TIN last four only.

## T-02-T20 additions (DEC-1471)
- **The K-1 set** arrives through the bridge: `POST /v1/tax-returns/{id}/engine-imports` kind `k1_set` (a person's upload, `engine_import.create`; `engine_sync_events.kind` gains `k1_set`, 0565). The manifest is JSON: `engine_return_id`, `version`, `is_final`, `form` (`1065`, `1120s`, `1041`), `tax_year`, optional `period_start`/`period_end`, and `recipients[]` (`ref`, `name`, `kind` gp/lp/shareholder/beneficiary, `is_entity`, `tin_last4`, `tin_kind`, `address{}`, `ownership_note`, `k3` included/not_required/not_included, `states[]`, `documents[]` {`kind` k1/k3/state_k1/letter, `jurisdiction` for a state K-1, `file_name` of an engine PDF already imported on this return}, `box_lines[]` {`document_kind`, `box_code`, `description`, `amount` as a decimal string, `is_total`}). 422 `k1_set_invalid` (`facts.reason`: `full_tin` when any nine-digit TIN appears, or the field at fault) and `k1_document_missing`. Engine PDF names may carry a recipient suffix (`2025P_Ridgeline_V2_k1_p01.pdf`, `k3_`, `state_k1_il_`, `letter_`), filed as the K-1 family.
- Applying a set: recipients by `ref`; a new package version per recipient (`draft`); a newer set supersedes a draft, and after release names the released package (`supersedes_package_id`). Documents are marked `is_draft` unless the set is final.
- `GET …/k1-packages`: `items` with `documents` (additive on `K1PackageOut`), `counts` by status (the tiles). `GET /v1/k1-packages/{pid}`: box lines only for readers of the return's content. `…/documents/{doc}`: the SHL-08 manifest.
- `POST …/k1-packages:share-internal`: one hand-off per package and target (`draft_shared`), an `internal_handoff` evidence copy in the target's scope (Source documents), fulfilling the target's one open request titled for a K-1 from this issuer, and a `draft_k1` final-approval blocker until the release replaces the draft. The sharer must read both returns (404 otherwise); TAX-02's `k1_dependencies` shows the source only to a reader of both (DEC-88). 409 `k1_not_shareable`.
- `GET …/k1-packages/release-check`: codes `not_final_approved`, `no_packages`, `final_k1s_missing`, `nothing_to_release`; T21 adds the firm's release condition.
- `POST /v1/k1-packages/{pid}:resend`: a released package only (409 `k1_not_released`); records the contact and emits `schedule_k_package.resend_requested` for T21's workflow.
- Details changes: `GET /v1/k1-recipients/{rid}/details-changes`; `:accept` / `:reject` once, by a person (0565's trigger; 409 `details_change_decided`).


## T-02-T21 additions (DEC-1476)
- `GET …/k1-packages/release-check` adds `no_release_policy` (BH-TAX-02 names no signer for the issuing client today) and `recipient_contact_missing` (a ready package has neither a delivery contact nor a recipient contact).
- `POST …/k1-packages:release` (202, `Idempotency-Key`): `package_ids` must be the check's ready packages (409 `k1_release_ineligible`, `facts.failing` the codes or `packages_not_ready`); `seen_version` must be at least the newest `version_no` among them and `email_template_version_id` the firm's `deliverable_ready` version in use (409 `stale_version`). The answer is the release `pending` with `not_before` = now + 10 s. A person with a fresh second factor only; agent, system, support and the policy principal 403.
- `POST /v1/k1-releases/{rid}:undo`: the requester before `not_before` (409 `undo_window_closed` after, or for anyone else; 409 `effect_started` once the workflow consumed the grant). The answer is the release `undone`.
- After the window, `K1ReleaseWorkflow` per package: the contact, a `k1_recipient` grant on the package (a pending grant and a contact invitation when the contact has no portal person yet), `released`, one "Deliverable ready" email (`deliverable_ready`, no amounts) and the hand-off drafts on other returns replaced by the final with its K-1 box values in `final_values`. The release ends `completed`, or `failed` with a code.
- `schedule_k_package.resend_requested` gives the corrected contact the grant or invitation and a new "Deliverable ready" email.
- A `k1_recipient` grant's `k1_package` scope resolves to the issuing return (the portal reads check the grant's own package, T26).
