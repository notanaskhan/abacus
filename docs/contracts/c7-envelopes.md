# C7 Envelope service (v1 draft)

| Field | Value |
|---|---|
| Register row | C7 |
| Version | v1 |
| Status | stub (N-02-T03, 2026-10-27): every route 404 with `signatures.envelopes` off, 501 with it on |
| Provider epic | N-02 |
| Consumers | F-06 (signatures shell), T-01 (8879 family, consents "1 of 2 signed"), T-02, P-07 (G3 letter gate), A-07 (governance letters), N-04 (notice responses), I-01 (activity, `signatures_out` home count), R-02 |
| Freeze sprint | S15 Contract Monday (Mon May 17, 2027) |
| Flags | `signatures.envelopes` (hub, import, portal reads); later `signatures.docusign`, `signatures.kba_8879`, `engagements.letter_composer` |
| Spec | SPEC-381; `docs/plan/epics/N-02.md` §3, §4 |
| ADRs | ADR-149 (P-26), ADR-150 (W7), ADR-161 (grants and Undo), ADR-158, ADR-152 amendment (proposed) |

## 1. Purpose
One envelope model for every signed document, whichever provider: `record` (imported, already signed), `docusign` (embedded signing) or `fake` (synthetic tenants). Sources (engagement letters, consents, e-file authorizations, rep letters, notices) register with `signatures.api.register_envelope_source` and get their gate facts back.

## 2. Callers and actions
| Operation | Method and path | Matrix action | Agent / system |
|---|---|---|---|
| List, summary, drawer | `GET /v1/envelopes`, `/v1/envelopes/summary`, `/v1/envelopes/{id}` | `envelope.read` | agent: `task_scope` |
| Draft, edit, validate, resend | `POST /v1/envelopes`, `PUT /v1/envelopes/{id}`, `POST …/validate`, `POST …/resend` | `envelope.draft` | **agent: allow (draft only)**, system: allow |
| Page preview | `GET /v1/envelopes/{id}/documents/{doc}/pages/{n}` | `envelope.read` | — |
| Send, Undo | `POST /v1/envelopes/{id}/send`, `/send/undo` | `envelope.send` | deny |
| Remind | `POST /v1/envelopes/remind/preview`, `/remind/send` | `envelope.remind` | deny |
| Void | `POST /v1/envelopes/{id}/void` | `envelope.void` | deny |
| Reveal a signer's IP | `POST /v1/envelopes/{id}/signers/{sid}/reveal-ip` | `signer.reveal_ip` (fresh MFA, onshore) | deny |
| Evidence package | `GET /v1/envelopes/{id}/evidence.zip` | `envelope.evidence_download` | deny |
| Record-mode import | `POST /v1/envelopes/import` | `envelope.import_record` | deny |
| Record-mode import file (N-02-T08, DEC-818): the raw bytes, `?filename=`; scanned before storage, refused closed; answers `ImportFileOut` whose `id` an import names in `upload_ids` (the first is the completed document) | `POST /v1/envelopes/import/files` | `envelope.import_record` | deny |
| Wet signature | `POST /v1/envelopes/{id}/signers/{sid}/wet-signature` | `envelope.record_wet_signature` | deny |
| Countersign session | `POST /v1/envelopes/{id}/countersign/session` | `envelope.countersign` | deny |
| Policies | `GET /v1/envelope-policies`, `PUT /v1/envelope-policies/{family}` | `envelope_policy.read`, `envelope_policy.manage` | deny |
| Portal list, view, pages, viewed, progress | `GET /v1/portal/envelopes`, `GET /v1/portal/envelopes/{id}`, … | `portal_envelopes.read` | deny |
| Portal ERSD, signing session, return | `POST /v1/portal/envelopes/{id}/esign-consent`, `/signing-session`, `GET …/signing-session/{sid}/return` | `portal_envelopes.sign` | deny |
| Portal decline, withdraw | `POST /v1/portal/envelopes/{id}/decline`, `/decline/withdraw` | `portal_envelopes.decline` | deny |
| Portal signed copy | `GET /v1/portal/envelopes/{id}/download` | `portal_envelopes.download` | deny |
| Letter (ENG-04) | `GET /v1/engagements/{id}/letter/composer`, `PUT …/letter/composer`, `GET …/letter/compare`, `GET …/letter/pdf`, `POST …/letter/request-approval`, `…/approve`, `…/send`, `…/amend` | `letter.read`, `letter.draft`, `letter.approve`, `letter.send`, `letter.amend` | agent: `letter.draft` only |

The plan's `portal.envelopes.*` are spelt `portal_envelopes.*` (one dot, DEC-139). The composer lives under `/letter/composer` because `PUT /v1/engagements/{id}/letter` is the kept record path (`letter.record`).

## 3. Status words
`envelope` (draft, sent, viewed, partially_signed "{signed} of {total} signed", completed, declined, expired, voided) and `envelope_signer` (pending, viewed, signed, declined, verification_failed) in `docs/product/status-vocabulary.yaml`; the Letter object (`letter`) and the superseded marker with N-02-T05.

## 4. Human-only actions
`envelope.send`, `envelope.remind`, `envelope.void`, `envelope.import_record`, `envelope.record_wet_signature`, `envelope.countersign`, `envelope.evidence_download`, `signer.reveal_ip`, `envelope_policy.manage`, `letter.approve`, `letter.send`, `letter.amend`, every `portal_envelopes.*` verb.

## 5. Audit events
`envelope.created`, `envelope.updated`, `envelope.validated`, `envelope.sent`, `envelope.send_undone`, `envelope.viewed`, `envelope.reminded`, `envelope.voided`, `envelope.expired`, `envelope.declined`, `envelope.decline_withdrawn`, `envelope.completed`, `envelope.imported`, `envelope.superseded`, `envelope.retention_extended`, `signer.esign_consent_accepted`, `signer.kba_failed`, `signer.verification_failed`, `signer.signed`, `signer.countersigned`, `signer.wet_signature_recorded`, `signer.ip_revealed`, `evidence.downloaded`, `signed_copy.downloaded`, `envelope_policy.updated`, `write_capability.executed`, `letter.*` (N-02 §4.6). Identifiers only.

## 6. Reserved provider fields
`provider_envelope_id`, `provider_recipient_id`, `signing_session` (`{session_id, presentation, url, expires_at}`) and `outcome` on the portal view are present in v1 and null until `signatures.docusign` (N-02-T18 onward). A record-mode envelope never has them.

## 7. Module API
`signatures.api.register_envelope_source(kind, resolver)`, `envelope_summary_for(ctx, source_kind, source_id)`, `envelope_gate_facts(ctx, gate_kind, target_ref)` (G3, e-file authorization), `file_signed_copy` through `evidence.api.file_to_folder` (Signed authorizations).

## 8. Stub
Models and routes: `backend/src/abacus/modules/signatures/contract.py` (`/v1/envelopes*`, `/v1/envelope-policies*`, `/v1/portal/envelopes*`) and `backend/src/abacus/modules/engagements/letter_contract.py` (`/v1/engagements/{id}/letter/composer`, `compare`, `pdf`, `request-approval`, `approve`, `send`, `amend`). `envelope_signer` and `letter` status words are in the vocabulary.
