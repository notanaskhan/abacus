# §7216 consent gate and the tax-profile family (C19 v1)

| Field | Value |
|---|---|
| Register row | C19 (`docs/contracts/README.md`) |
| Version | v1 |
| Status | stub (T-01-T01, 2026-10-29): every route 501 behind its flag; module API raises `NotImplementedError` |
| Provider epic | T-01 |
| Consumers | T-02 (TAX-02 consent chip), T-03 to T-08, N-04, W-02, I-02, G-02 (ADM-04 D), P-07 (CLI-02 b), P-06 (BND-01 tag), the AI gateway (condition 6) |
| Freeze sprint | S17 |
| Flags | `consents.registry` (consents and templates), `clients.tax_profile` (tax profile, elections, authorizations, transcripts) |
| Spec | SPEC-501 AC-1 to AC-4; `docs/plan/epics/T-01.md` §3.1–§3.6, §4.3 |
| ADRs | ADR-005, ADR-031, ADR-050, ADR-052; DEC-52, DF-16, DF-31 |

## 1. Purpose
One purpose per signed document (Treas. Reg. §301.7216-3): `use`, `ai_disclosure`, `offshore_disclosure`, `third_party_disclosure`, `other_services_use`, `firm_defined`, for named tax years. **Condition 6:** TRI never reaches a model unless the taxpayer's `use` and `ai_disclosure` consents are signed and in force for the year (`tri_consent_verdict`); the boundary refuses with reason `consent_7216`.

## 2. Who may call it
| Operation | Method and path | Action | Flag |
|---|---|---|---|
| Registry | `GET /v1/consents?status=&purpose=&tax_year=&offshore=` | `consent.read` | `consents.registry` |
| Counts | `GET /v1/consents/summary` | `consent.read` | `consents.registry` |
| Detail | `GET /v1/consents/{id}` | `consent.read` | `consents.registry` |
| Evidence (audited) | `GET /v1/consents/{id}/documents/{doc}/evidence` | `consent.evidence_download` | `consents.registry` |
| Request (C7 draft, one document per purpose; 409 `consent_declined`, 422 `one_purpose_per_document`) | `POST /v1/consents/requests` | `consent.request` | `consents.registry` |
| Renew | `POST /v1/consents/renewals` | `consent.request` | `consents.registry` |
| Record mode, decline, revoke (fresh MFA) | `POST /v1/consents/records`, `/{id}/declines`, `/{id}/revocations` | `consent.record` | `consents.registry` |
| Export (async CSV; fresh MFA) | `POST /v1/consents/exports` (202) | `consent.export` | `consents.registry` |
| Per taxpayer | `GET /v1/client-entities/{id}/consents` | `consent.read` | `consents.registry` |
| Templates (counsel-attested; fresh MFA) | `POST /v1/consent-templates/imports`, `/{id}/publish` | `consent_template.manage`, `.publish` | `consents.registry` |
| Tax profile | `GET /v1/client-entities/{id}/tax-profile` | `tax_profile.read` | `clients.tax_profile` |
| Elections | `PUT /v1/client-entities/{id}/elections/{kind}` | `tax_election.manage` | `clients.tax_profile` |
| Authorizations | `GET`/`POST /v1/client-entities/{id}/authorizations`, `POST …/authorizations/requests` | `tax_authorization.manage` | `clients.tax_profile` |
| Transcripts | `POST /v1/client-entities/{id}/transcripts`, `POST /v1/transcripts/{id}/comparisons` | `transcript.upload`, `.compare` | `clients.tax_profile` |

Every action denies the agent, the system and client principals. Files are upload intents (`upload_ids`).

## 3. Status words
`consent`: requested ("Requested · n of m signed") · signed (with expiry) · expiring (derived) · expired · declined · revoked · superseded. `tax_authorization`: requested · on_file · expired · revoked. Registry rows land with T-01-T06.

## 4. Module API
`organisations.api.consent_state(tenant, entity_ids, purpose, tax_year) -> list[ConsentState]`; `organisations.api.tri_consent_verdict(tenant, subjects, at) -> TriVerdict(valid, missing)` (fail closed; p95 ≤ 15 ms).

## 5. Audit and outbox
Audit: `consent.requested`, `.signer_signed`, `.signed`, `.recorded`, `.declined`, `.revoked`, `.expired` (system), `.renewal_drafted`, `.exported`, `.evidence_downloaded`, `consent_template.imported`, `.published`, `tax_authorization.added`, `.requested`, `tax_election.updated`, `transcript.uploaded`, `.compared`, `ai.boundary_refused` (`consent_7216`). Outbox: `consent.requested`, `.signed`, `.declined`, `.revoked`, `.expired` (identifiers and enums only).

## 6. Classification
Consent rows `confidential`; return and transcript figures TRI (`restricted`, `x-tri`); CAF last four only; no TIN.
