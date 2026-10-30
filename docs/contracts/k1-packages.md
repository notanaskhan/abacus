# K-1 packages (v1; C5 additive v1.x)

| Field | Value |
|---|---|
| Version | v1 |
| Status | stub (T-02-T02, 2026-10-29): every route 501 behind `tax.k1_release` |
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
