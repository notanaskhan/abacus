# Tax-engine bridge (v1)

| Field | Value |
|---|---|
| Version | v1 |
| Status | stub (T-01-T02, 2026-10-29): every route 501 behind its flag |
| Provider epic | T-01 |
| Consumers | T-02 (TAX-02 sync chip, status machine), P-04 (SHL-12 h final approval), T-08, W-01 |
| Flags | `tax.engine_bridge` |
| Spec | SPEC-501 AC-5 to AC-8; `docs/plan/epics/T-01.md` §3.7–§3.10, §4.3 |
| ADRs | ADR-231 (the engine of record computes), ADR-052 (hostile engine files), ADR-040 (connectors read; W2 is a file the firm carries) |

## 1. Purpose
CCH Axcess Tax is the engine of record; the link is a **file bridge** (W2 `cch_axcess_tax.export_file`, mode `file`, no egress host). Accrued exports a workbook only after final approval and imports engine files through a diff a person approves.

## 2. Routes
| Operation | Method and path | Action |
|---|---|---|
| Final-approval facts and blockers | `GET /v1/tax-returns/{id}/final-approval` | `tax_return.read` |
| Final approval (L4 `final_approval` sign-off; only `tax/approval.py`) | `POST /v1/tax-returns/{id}/final-approval` `{seen_checkpoint_id, content_hash}` | `tax_return.approve` (`function_in(signer)`; BH-TAX-02's approver in the service) |
| Sync chip, history, diagnostics | `GET /v1/tax-returns/{id}/engine-sync` | `tax_return.read` |
| Export (consumes the write grant) | `POST /v1/tax-returns/{id}/engine-exports` | `tax_return.export` |
| Audited download · a person marks it exported | `GET /v1/engine-exports/{id}/file` · `POST …/mark-exported` | `tax_return.export` |
| Upload an engine file (`values`, `diagnostics`, `pdfs`, `acks`) | `POST /v1/tax-returns/{id}/engine-imports` | `engine_import.create` |
| Diff · approve · reject | `GET /v1/engine-imports/{id}` · `POST …/approve` · `POST …/reject` | `tax_return.read` · `engine_import.approve` |
| Settings (locked cells), mappings (409 `mapping_conflict`), format check | `GET`/`PUT /v1/firm/integrations/{key}/settings`, `PUT …/user-mapping`, `…/office-mapping`, `…/status-mirror`, `POST …/test` | `integration.read`, `integration.configure` (fresh MFA), `integration.test` |

## 3. Sync-chip states
not_yet_exported · ready_for_export · exporting · synced · out_of_sync · import_pending_approval · failed (the registry's `return_sync_chip`).

## 4. Module API
`tax.api.final_approval_blockers(return_id)`, `tax.api.register_final_approval_blocker(kind, provider)` (T-02 registers the draft K-1 blocker); raise until T-01-T27.

## 5. Events
Outbox: `tax_return.approved`, `engine_sync.exported`, `engine_sync.failed`, `engine_sync.imported`, `engine_import.pending_approval` (identifiers and counts only). Audit: `return.final_approved`, `engine_export.generated`, `.downloaded`, `.marked_exported`, `engine_import.uploaded`, `.approved`, `.rejected`, `engine.diagnostic_received`, `integration.settings_updated`, `.mapping_updated`, `.tested`.

## 8. ADM-08 settings, live since T-01-T20
Cells (stored as `integration_mappings`): `return_id_template` (default `{Tax year}{Type}:{Client code}:V{n}`; must keep `{Tax year}`, `{Client code}` and end `:V{n}`), `client_code_rule`, `type_letter.<form>`, `who_may_export` (`reviewer_manager_signer`, `manager_signer` or `signer`: narrower only), and the locked `export_after_final_approval`, `import_requires_approval` (`stricter_only`) and `status_push` (`file_mode_has_no_push`). Mappings replace the kind's rows; `workflow_status` keys are return status codes. Every save carries the install's `version`. 409 `setting_locked`, `mapping_conflict`, `stale_version`; 422 `setting_invalid`. `POST …/test` returns codes only (`no_engine_file`, `check_failed`, or the holder's) and `returns_read` (additive).
