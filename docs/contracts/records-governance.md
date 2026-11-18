# Records governance v1 — retention policy versions, holds, destruction batches and certificates

| Field | Value |
|---|---|
| Owner | evidence (Q-05; SPEC-711), extending Q-02's compliance kernel (`compliance-kernel.md` v1.1) |
| Status | skeleton (Q-05-T01, 2026-11-18; DEC-5608); stub Q-05-T03; v1 S53 |
| Code | `backend/src/abacus/modules/evidence/records_governance_contract.py` (Q-05-T03) |
| Flag | `records.governance` (default off; off: 404; on: 501 until each build task); kill switch `destruction_execute` |
| Consumers | FIL-02, FIL-01 (N-01 views), R-03 (POR-18 intake store), N-03 (message threads) |

Q-02's `retention_policy_versions` and `legal_holds` are extended, never redefined (AC-32). Destruction is dual-approved by a `firm_admin` and a `security_admin` (distinct person and role), with typed confirmation and fresh MFA, a per-item hold re-check, version deletion on primary and replica through the destruction role (OQ-1, amendment Q-05-T32), tombstones and a deterministic certificate. The agent never destroys, approves or places a hold.

| Method and path | Action | Notes |
|---|---|---|
| `GET /v1/retention/summary` | `retention.read` | tiles, last certificate |
| `GET /v1/retention/policies/{id}/versions` · `POST /v1/retention/policies` | `retention.read` · `retention_policy.manage` | a policy below the legal minimum is refused; "+ New policy" is a service-line override (OQ-11) |
| `GET /v1/legal-holds` · `POST /v1/legal-holds` · `POST …/{id}/release` | `legal_hold.read` · `legal_hold.place` · `legal_hold.lift` | Q-02 routes, body extended with `display_name`, `document_classes`, `until_released` |
| `GET /v1/destruction-batches?status` · `GET …/{id}` | `retention.read` | batches and history |
| `GET /v1/destruction-batches/{id}/documents.csv` | `destruction.export_list` | audited export, fresh MFA |
| `POST /v1/destruction-batches/{id}/approvals` | `destruction.approve` | the second carries `confirmation` (`DESTROY ‹ref›`); 409 `same_approver`, `approver_role_taken`, `batch_phrase_mismatch` |
| `POST /v1/destruction-batches/{id}/cancel` | `destruction.approve` | API and runbook only (OQ-12) |
| `GET /v1/destruction-certificates/{id}` | `retention.read` | the PDF (C11) |
| any read of a destroyed version | the route's own action | 410 `destroyed` with `certificate_ref` |

**Examples (foot):** batch 2026-Q3 1,204 documents of 31 former clients; fil02e 1,204 − 3 = 1,201 destroyed; certificate DC-2026-Q3.
