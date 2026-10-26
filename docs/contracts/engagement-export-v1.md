# Engagement export format and routes (v1)

| Field | Value |
|---|---|
| Register row | Screen-family contract "Engagement export" in `docs/contracts/README.md` |
| Version | v1 (format `accrued.binder-export` 1.0) |
| Status | create, undo, history and status live (A-01-T18, 2026-10-26); package built by A-01-T19; download a stub until A-01-T22 |
| Provider epic | A-01 (T17 stub; T18 create, undo, reads; T19 package; T22 download) |
| Consumers | AUD-02, AUD-03 export sheet (A-01-T24); Q-04 rollback path; G-02 and Q-02 firm export (one package per engagement); A-07 archive seal manifest base (P-43); A-04, A-05, A-06 workpaper sections; requests (index rows) and agents (screening) section providers |
| Freeze sprint | S11 (Fri Apr 2, 2027) |
| Flag | `audits.binder_export` (default off, expires 2027-04-21) |
| Spec | `docs/specs/SPEC-344-engagement-export-format.md` |
| ADRs | ADR-036, ADR-031, ADR-052, ADR-104, ADR-139; P-35, P-43 |

## 1. Purpose
Consumers can rely on one open package format for an audit engagement's PBC binder (SPEC-344 §7): a fixed layout, `manifest.json` validated by the generated schema `docs/contracts/schemas/engagement-export-manifest-v1.schema.json`, `sha256sum`-format checksums, a v1 index column list, four provenance files and a named-section slot. The five routes below create, undo, read and download an export.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Create (`Idempotency-Key`, 202) | `POST /v1/work-items/{work_item_id}/exports` | `export.create` | engagement partner, manager; fresh MFA, independence, not offshore | denied |
| History | `GET /v1/work-items/{work_item_id}/exports` | `export.read` | engagement partner, manager; independence | denied |
| Status poll | `GET /v1/exports/{export_id}` | `export.read` | as above | denied |
| Undo (10-s window) | `POST /v1/exports/{export_id}/undo` | `export.create` | as create | denied |
| Download (`Range`) | `GET /v1/exports/{export_id}/download` | `export.download` | engagement partner, manager; fresh MFA, independence, not offshore; and the requester or an `export.create` holder on the engagement (service) | denied |

Platform support holds no export cell (SPEC-012: support roles are read-only); client principals reach none (INV-4). Flag off: 404. Create, undo and the reads are live (A-01-T18; DEC-435); download answers 501 `not_implemented` until A-01-T22.

Module interface: `evidence.api.register_export_section(name, provider, *, section_version="1.0")` with `SectionRequest` and `SectionFile`; core names `index`, `fulfilments`, `review_decisions`, `screening`, `citations`; reserved `readme`, `manifest`, `checksums`, `evidence`, `audit_trail` (SPEC-344 §6). `SectionRequest` names the requester (`requested_by_user_id`, `membership_id`): a provider reads as that person (`visible()`, walls, independence) and never emits a Restricted value unmasked (DEC-379); it names each binder once, and every binder id has been checked against the work item at create.

Stubs check the flag before anything else, as every stub on main does; the implementing tasks authorise first (a wall answers 404 before the flag or any read).

## 3. Models
Code: `backend/src/abacus/modules/evidence/export_contract.py` (routes) and `export_manifest.py` (format).

- `ExportCreateIn` `{kind: binder|final_binder = binder (internal), scope: ExportScopeIn (internal)}`.
- `ExportScopeIn` `{binder_ids: uuid[] ≤ 50 (internal; empty = every PBC binder of the work item), include_unaccepted = false (internal), include_audit_trail = true (internal)}`.
- `EngagementExportOut` `{id, engagement_id, work_item_id, kind, scope: ExportScopeOut, format_version "1.0" (public), status: EngagementExportStatus, requested_by {user_id (internal), display_name (confidential)}, requested_at, not_before, ready_at?, expires_at?, request_count?, file_count?, size_bytes?, manifest_sha256?, bundle_sha256?, failure_code? (integrity_mismatch | export_section_missing | build_error), void_reason? (withdrawn_content | expired), allowed_actions: (undo | download)[]}`; all internal unless noted.
- `EngagementExportPageOut` `{items: EngagementExportOut[] ≤ 50, next_cursor?}`, newest first.
- `EngagementExportManifest` (`manifest.json`; SPEC-344 §7.4): identifiers internal; `firm_name`, client and engagement names, `requested_by` and file paths confidential; `format` and `format_version` public.

## 4. Status words
C2 `engagement_export` (`docs/product/status-vocabulary.yaml`): `queued` "Queued", `packaging` "Packaging…", `ready` "Ready" (sheet: "Download · {n} files · {size} · expires {date}"), `failed` "Export failed", `expired` "Expired", `undone` "Undone".

## 5. Human-only actions
`export.create` and `export.download` are denied to the agent and system principals at the matrix (INV-1); T18's `engagement_exports.requested_by_kind CHECK = 'human'` refuses any other writer at the database.

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not_found"}` | flag off; outside the tenant or behind a wall |
| 403 | `{"detail": "forbidden"}` | role, independence, `offshore`, or stale MFA (`mfa_required`) |
| 409 | `{"detail": "undo_window_closed"}` | Undo after `not_before`, or by anyone but the requester |
| 409 | `{"detail": "effect_started"}` | Undo once the build consumed the grant |
| 409 | `{"detail": "export_not_ready"}` | download before `ready` |
| 410 | `{"detail": "export_expired"}` | download after 7 days or once voided |
| 422 | `{"detail": "export_kind_unsupported"}` | a work item that is not an audit (fail closed until C19) |
| 422 | `{"detail": "binder_not_in_work_item"}` | a scope binder id that is not one of the work item's PBC binders (DEC-379) |
| 501 | `{"detail": "not_implemented"}` | download, until A-01-T22 |

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `engagement_export.requested` | create | export id, work item id, kind, scope ids |
| `engagement_export.undone` | Undo | export id |
| `engagement_export.packaged` | built | counts, bytes, bundle and manifest SHA-256 |
| `engagement_export.failed` | build fails | failure code |
| `engagement_export.downloaded` | download | bytes sent, range |
| `engagement_export.expired` / `voided` | 7 days, withdrawn content | export id, reason |

Outbox: `engagement_export.requested`, `.ready`, `.failed`, `.expired`, `.undone` (identifiers only); notifications consumes `ready` and `failed`.

The build also records `engagement_export.started` (the grant consumed, status `packaging`) and `engagement_export.snapshotted` (`as_of_seq`, file and request counts) as the system on behalf of the requester (DEC-436).

**Build (A-01-T19; DEC-436):** `EngagementExportWorkflow` (`engagement_export:<tenant>:<export_id>`, batch) starts from `engagement_export.requested`, sleeps out the window, consumes the grant, snapshots the selection at one audit sequence into `engagement_export_contents`, builds the ZIP with `generated_at` = the export's `not_before` (so a rebuild of the same export is byte-identical), and stores it sealed in 64 MiB segments under `exports/<tenant>/<export_id>/segment-NNNN` in the exports bucket (`exports_bucket`). `audit_trail/events.jsonl` needs the audit trail's reader registered through `evidence.api.register_export_audit_trail`; without it a build that includes the trail fails `export_section_missing`.

## 8. Example payloads
Northwind's binder after Ana Cruz's acceptance, requested by Hannah Leclerc on Mon Sep 14, 2026 at 9:39 AM CT, ready at 9:40 AM (Brightwater Hale, synthetic):

```json
{
  "id": "6f1c…", "kind": "binder", "format_version": "1.0", "status": "ready",
  "scope": {"binder_ids": ["…"], "include_unaccepted": false, "include_audit_trail": true},
  "requested_by": {"user_id": "…", "display_name": "Hannah Leclerc"},
  "requested_at": "2026-09-14T14:39:50Z", "not_before": "2026-09-14T14:40:00Z",
  "ready_at": "2026-09-14T14:40:12Z", "expires_at": "2026-09-21T14:40:12Z",
  "request_count": 24, "file_count": 12, "size_bytes": 18874368,
  "allowed_actions": ["download"]
}
```
Its manifest lists 12 evidence files (3 + 5 + 3 + 1), `counts.requests_without_file = 12`, the four provenance files, `README.txt`, `index.csv`, `index.xlsx` and `audit_trail/events.jsonl`. The test `test_ac5_the_northwind_example_is_a_valid_v1_manifest` builds it.

## 9. Consumer contract tests
`backend/tests/contracts/engagement_export/test_engagement_export_v1.py` (stub gates, matrix, classification, manifest and schema, section slot). The export sheet's TypeScript fixture assertions arrive with A-01-T24 in `apps/web/src/fixtures/contracts/`.

## 10. Versioning
Additive changes in place. A format change a v1 reader cannot read is v2: a new model, a new schema file, one release of overlap; the v1 schema file is never rewritten (SPEC-344 §8).

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | (Fri Apr 2, 2027, planned) | | stub A-01-T17 |

## 11. Open points
Decided in DEC-376 (stub shapes, Undo under `export.create`, 202 on create, flag-first gate). The schema file is not yet in `.claude/hooks/_protected.py`'s generated list (protected path; add it with the next protected bundle).
