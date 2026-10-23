# Retention policies (v1)

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md` (the retention part of Q-02's compliance kernel) |
| Version | v1 |
| Status | live (Q-02-T23, 2026-10-23) |
| Provider epic | Q-02 (`evidence`) |
| Consumers | ADM-06h (read-only floors), FIL-02a (policies), Q-02-T24 (Object Lock retain-until), Q-05 (holds) |
| Freeze sprint | the sprint review after this change |
| Flag | none: the policy routes read and write firm settings that exist from the first published set |
| Spec | Q-02 §4.2 (`docs/plan/epics/Q-02.md`), AC-30 |
| ADRs | ADR-004, ADR-031; DEC-76 / P-62; DEC-156 |

## 1. Purpose
A firm keeps each record type for at least the published legal floor, and for its own policy where that is longer. Floors and the default policy set are platform content: staff import a numbered set and a second staff member publishes it. No floor or year count lives in code or a migration.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Read the firm's effective policies | `GET /v1/retention/policies` | `retention_policy.read` (the plan's `retention.read`; DEC-227) | every firm role: firm admin, security admin, quality partner, practice leader, partner-level members, and engagement roles on the firm's active engagements; clients denied | denied |
| Save one policy | `PUT /v1/retention/policies` | `retention_policy.update` (the plan's `retention_policy.manage`; fresh MFA) | firm admin, security admin | denied |
| Import a floor set (draft) | `POST /v1/platform/retention/floors` → 201 | staff issuer (`STAFF`) | platform staff | n/a |
| Publish a floor set | `POST /v1/platform/retention/floors/{set_version}/publish` | staff issuer | a different staff member from the importer | n/a |
| Import a default-policy set (draft) | `POST /v1/platform/retention/defaults` → 201 | staff issuer | platform staff | n/a |
| Publish a default-policy set | `POST /v1/platform/retention/defaults/{set_version}/publish` | staff issuer | a different staff member | n/a |

## 3. Models
Code: `backend/src/abacus/modules/evidence/retention_routes.py`. All Internal.
- **`RetentionPolicyOut`**: `record_type`, `service_line` (`audit`, `tax`, `cas`, `advisory`, `any`), `legal_floor_years` (decimal string or null), `anchor`, `authority`, `firm_years` (decimal string), `clock_start_event`, `lock`, `basis`, `version` (null when no firm policy exists), `source` (`policy` or `floor`). Where a firm has no policy, the floor applies and is returned as `source: floor`.
- **`RetentionPolicyIn`**: `record_type`, `service_line`, `firm_years` (> 0, one decimal place), `clock_start_event`, `lock`, `basis` (one line, at most 500).
- **`RetentionFloorSetIn`** / **`RetentionDefaultSetIn`**: `set_version` and 1 to 500 rows. A published set supersedes the previous published set of its kind, completely.
- Anchors and clock-start events: `upload`, `report_release`, `filing_date`, `due_or_received_later`, `relationship_end`, `client_inactive`, `message_date`, `event_date`, `period_end`.

## 4. Status words
Set status: `draft`, `published`, `superseded` (database only; not shown in the product yet).

## 5. Human-only actions
Saving a policy denies `agent` and `system`; `retention_policy.updated` is in the human-only register (Q-02-T30, migration 0125), so the database refuses it from an agent or policy actor. Publishing a set needs a second, different staff member (the database refuses the importer).

## 6. Errors
| Status | Body | When |
|---|---|---|
| 422 | `{"detail": "below_floor"}` | `firm_years` under the published floor for the record type (its service line, else `any`) |
| 422 | `{"detail": "policy_locked"}` | shortening a policy that stays locked |
| 422 | `{"detail": "retention_set_invalid"}` | a set row that doesn't fit the shape |
| 409 | `{"detail": "retention_set_exists"}` | importing a set version that exists |
| 409 | `{"detail": "retention_two_person"}` | the importer publishing their own set |
| 404 | `{"detail": "not found"}` | publishing a version with no draft |
| 403 | `{"detail": "forbidden"}` | no action, or stale MFA on save |

## 7. Audit and outbox events
| Event | Written when | Payload |
|---|---|---|
| `retention_policy.updated` | a policy is saved | the new version |
| `retention_policy.defaults_applied` | provisioning (`retention_defaults_v1`) or the ops back-fill runs | rows applied |

Every policy change is also copied to the insert-only `retention_policy_versions`.

## 8. Example payloads
`PUT /v1/retention/policies` `{"record_type": "<a published record type>", "service_line": "audit", "firm_years": "7", "clock_start_event": "report_release"}` → `{"version": 1}`. Record types and years come from the published sets, never from this document.

## 8a. Retain-until and records (Q-02-T24; internal APIs, no HTTP)
- **Record classes** code stores, by code: `client_document`, `derived_rendering`, `chain_anchor`, `seal_manifest`, `consent_evidence`, `signature_evidence` (`evidence.api.RECORD_TYPES`). Floors and defaults name these codes; their years are content.
- `evidence.api.retain_until_for(tenant, record_type, service_line, anchor_at)`: the longer of the firm's policy and the published floor (its service line, else `any`), from the anchor, at 365.25 days a year; None when neither exists, and the evidence default (`evidence_retention_days`) applies.
- An upload is locked (GOVERNANCE) until at least its `client_document` expiry anchored at upload (provisional), never less than the default.
- `evidence.api.extend_retention_for(tenant, versions, record_type, service_line, anchor_at)`: an anchor event (report release, filing date) extends each stored version's lock; one `retention.extended` event as the system. The daily `RetentionClock` that applies registered anchor events waits for Temporal Schedules.
- `evidence.api.put_record(tenant, record_class, body, retain_until)`: the records bucket, Object Lock **COMPLIANCE**, written once. `evidence.api.anchor_chain(tenant, retain_until)` publishes the newest audit checkpoint hash there (`audit_chain.anchored`); `kernel.uow.chain.verify_anchor` checks it later. No records bucket configured: 503, never a fallback.

## 9. Consumer contract tests
`backend/tests/integration/test_retention_policies.py` (floors, two-person publish, below floor, lock, the floor fallback, defaults at provisioning and through the back-fill, no value in the migration); `backend/tests/integration/test_retention_object_lock.py` (lock at or after the policy expiry, an anchor event extends it, chain anchors in COMPLIANCE mode that refuse deletion, no records bucket fails closed).

## 10. Versioning
| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | | | live 2026-10-23 (Q-02-T23) |
