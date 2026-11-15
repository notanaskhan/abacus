# Confirmations (A-08 epic contract, v1)

| Field | Value |
|---|---|
| Register row | epic contract (A-08 §8.1), not a C-numbered contract |
| Version | v1 |
| Status | stub (A-08-T06) |
| Provider epic | A-08 (N for the public family, AY for firm routes) |
| Consumers | AUD-14, POR-17; W-04, G-03 and R-03 must treat `/v1/confirm/*` as a link-principal-only surface |
| Freeze sprint | S47 (A-08 §8.1) |
| Flag | `audits.confirmations` (default off, expires 2027-05-13); control `confirmation_links` (ADR-157) |
| Spec | `docs/specs/SPEC-657-a08-audit-fieldwork-depth.md` (F6, F7) |
| ADRs | ADR-146 (P-09), ADR-152 + amendment (P-45; proposed, DEC-5029), ADR-157 (P-66), ADR-050, ADR-052 |

## 1. Purpose
AU-C 505 external confirmations under the firm's control: AUD-14 creates, verifies addresses,
requests the client's authorization (C7), sends, reconciles, accepts and closes; POR-17 is the
respondent's one page. The client sees only the authorization it signs
(I-CONFIRMATION-ISOLATION). Code: `backend/src/abacus/modules/assurance/confirmations_contract.py`
(routes), `confirmations_contract_models.py` (models), `confirmations_fixtures.py` (POR-17 a–f).

## 2. Who may call it
Firm routes answer, in order: a client principal 404; the action on the work item's engagement
(walls 404, independence 403); 404 with `audits.confirmations` off; 501 `not_implemented` until
the task named in the handler.

| Operation | Method and path | Matrix action | Roles allowed | Agent / system |
|---|---|---|---|---|
| Log | GET `/v1/work-items/{wid}/confirmations` | `confirmation.read` | team, EQR | agent task_scope |
| Tiles and coverage | GET `…/confirmations/summary` | `confirmation.read` | team, EQR | agent task_scope |
| Create | POST `…/confirmations` (Idempotency-Key) | `confirmation.create` | EP, manager, senior | denied |
| Authorization | POST `…/confirmations/authorization` | `confirmation.request_authorization` | EP, manager, senior | denied |
| Export | GET `…/confirmations/export.xlsx` | `confirmation.export` | team | denied |
| Drawer | GET `/v1/confirmations/{cid}` | `confirmation.read` | team, EQR | agent task_scope |
| Address verification | POST `…/{cid}/address-verifications` | `confirmation.verify_address` | EP, manager, senior, staff | denied |
| Send · second request · revoke | POST `…/{cid}/send` · `/second-request` · `/revoke-link` | `confirmation.send` (409 `address_not_verified`, `authorization_missing`) | EP, manager, senior | denied |
| Recorded response | POST `…/{cid}/record-response` | `confirmation.record_response` | EP, manager, senior | denied |
| Reconciliation | POST `…/{cid}/reconciliation` | `confirmation.reconcile` | EP, manager, senior, staff | denied (proposes via `suggestion.create`) |
| Accept reconciliation | POST `…/{cid}/accept-reconciliation` | `confirmation.accept_reconciliation` (`not_preparer_of_target`) | EP, manager, never the reconciler | denied |
| Alternative procedures | POST `…/{cid}/alternative-procedures` | `confirmation.record_alternative` | EP, manager, senior | denied |
| Exception prefill | POST `…/{cid}/exception` | `finding.create` | as A-06 | as A-06 |
| Close | POST `…/{cid}/close` | `confirmation.close` | EP, manager | denied |
| Respondent preview | GET `…/{cid}/respondent-preview` | `confirmation.read` | team | agent task_scope |
| Respondent page | GET `/v1/confirm/{token}` | marker `link_principal` → `confirmation.respond_view` (`link_scope_only`) | link principal only | denied |
| Email code · verify | POST `/v1/confirm/{token}/code` · `/code/verify` | → `confirmation.respond_verify` | link principal only | denied |
| Attachment | POST `/v1/confirm/{token}/attachments` | → `confirmation.respond` (`email_verified`) | link principal only | denied |
| Response | POST `/v1/confirm/{token}/response` (201; 409 `already_answered`) | → `confirmation.respond` (`email_verified`) | link principal only | denied |

**The public family (stub).** No session; the path token names one link principal. Until A-08-T15
resolves tokens through `identity_resolve_link`, the stub serves POR-17's synthetic fixtures in
`local` and `test` environments only. Every other token or environment answers `{"state":
"expired"}` (GET) or 404 (POST), after the same padded floor (`CONFIRM_PAD_SECONDS`, 0.4 s): unknown,
expired, revoked and paused links are indistinguishable (DV-7). The code request answers 202 for
any input. Nothing is written; the token is never logged.

## 3. Models
`confirmations_contract_models.py`. Every field carries a classification (checked by the contract
test). Money and respondent text are `confidential`; the email code is `restricted`; account
numbers are last four only. Firm: `ConfirmationLogOut` (rows with `allowed_actions`,
`links_paused`), `ConfirmationSummaryOut` (tiles summing to the log, `CoverageOut`),
`ConfirmationDetailOut` (lines, address verifications, response, `ReconciliationOut` with code's
`unreconciled`, classification and Below CT), inputs `ConfirmationCreateIn`,
`AddressVerificationIn` (≥ 1 source and citation), `AuthorizationIn`, `RecordedResponseIn`,
`ReconciliationIn`, `SeenHashIn`, `AlternativeProcedureIn`. Public: `RespondentViewOut` (`state`
open · expired · answered; one confirmation's `RespondentRequestOut` — firm, client, respondent
organisation, as-of date, the quoted authorization, balance, invoices, the bank variant's client
accounts — and nothing else), `RespondentResponseIn` (`attestation: true` required),
`RespondentReceiptOut` (the server's `difference`).

## 4. Status words
`confirmation`: Draft · Authorization requested · Sent · Responded · Exception · Alternative
procedures · Closed. `link_principal`: Issued · Opened · Locked · Answered · Expired · Revoked
(POR-17 shows only open, expired, answered). From `docs/product/status-vocabulary.yaml` (A-08-T01).

## 5. Human-only actions
Send, second request, revoke, reconcile, accept reconciliation, record alternative procedures and
close: the agent and system principals are denied at the matrix (generated I-AGENT-NEVER suite,
A-08-T03); `confirmation_decisions` carries the human-only CHECK and the decider ≠ reconciler
CHECK (A-08-T16). Respondent submissions are the link principal's, attributed with its verified
email fingerprint.
