# Audits cockpit host and slots (v1)

| Field | Value |
|---|---|
| Register row | Screen-family contract in `docs/contracts/README.md` (A-01 §8.1; chapter 01 may promote it into C1–C21) |
| Version | v1 |
| Status | stub (A-01-T02, 2026-10-24); PATCH profile and POST phase live behind the flag (A-01-T05, 2026-10-24); index, cockpit and Source Documents live behind the flag (A-01-T08 to T10, 2026-10-25); release and archive records live behind the flag (A-01-T23, 2026-10-27) |
| Provider epic | A-01 |
| Consumers | AUD-01, AUD-02, AUD-03 (A-01-T11, T12, T15); A-02 (Trial Balance section), A-03…A-09, P-09 / P-10 (dock host, rail sync by `work_item_ref`), K-04 (Board, gear), X-01 / X-03 (segments), I-01 (index counts) |
| Freeze sprint | S8 (freeze Fri Feb 19, 2027 per A-01 §8.1) |
| Flag | `audits.cockpit` (boolean, default off, expires 2027-04-21, DEC-137) |
| Spec | `docs/specs/SPEC-330-audits-cockpit.md` |
| ADRs | ADR-005, ADR-013, ADR-024, ADR-031, ADR-036, ADR-139 (P-36), P-04, P-39 |

Code: `backend/src/abacus/modules/assurance/audits_contract.py` (models and routes), `backend/src/abacus/modules/assurance/sections.py` (slots), C5 v1.1 row parts in `backend/src/abacus/modules/requests/contract.py` (`RequestOwedByOut`, `RequestLatestUploadOut`).

## 1. Purpose
Consumers can rely on an audits index on the P-36 envelope whose phase tiles (`counts`, minus the active tile) and segments (`facets.segment`) come from one `visible()` predicate and sum to `total`; a cockpit projection whose rail rows come only from registered section providers (an unregistered or provider-less section is never projected); a Source Documents aggregate across the work item's PBC binders; an EBP profile; and three human-only record writes (phase, external release, external archive). `$auditId` is the assurance work item (P-04). Later epics extend the cockpit through three slots without editing A-01.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal | Implemented by |
|---|---|---|---|---|---|
| AUD-01 index | `GET /v1/audits?segment=&type=&phase=&partner=&office=&due=&period=&q=&cursor=&limit=` | `engagement.read_metadata` | every firm role through `visible()`; the route refuses portal principals (INV-4) | refused | A-01-T08 |
| Cockpit | `GET /v1/audits/{work_item_id}/cockpit` | `engagement.read_metadata` | every firm role on the engagement; bands, dock tabs and actions only with `engagement.read` as well (metadata-only roles get the bar and overview only, DEC-312) | refused | A-01-T09 |
| EBP profile | `PATCH /v1/audits/{work_item_id}/profile` | `engagement.update` | engagement partner, manager | denied (no cell) | A-01-T05 |
| Record a phase | `POST /v1/audits/{work_item_id}/phase` (`Idempotency-Key`; 201) | `assurance.record_phase` | engagement partner, manager; independence | **denied** | A-01-T05 |
| Record an external release | `POST /v1/audits/{work_item_id}/release-record` (`Idempotency-Key`; 201) | `assurance.record_release` | engagement partner; `mfa_recent`; independence | **denied** | A-01-T23 |
| Record an external archive | `POST /v1/audits/{work_item_id}/archive-record` (`Idempotency-Key`; 201) | `assurance.record_archive` | engagement partner, manager; `mfa_recent`; independence | **denied** | A-01-T23 |
| Source Documents | `GET /v1/audits/{work_item_id}/source-documents?binder=&q=&sort=missing_first\|received_first` | `request_item.read` | as P-06 (`client_service` sees status and file names, never content) | refused | A-01-T10 |

Every route first authorises its action (a client principal, an agent or the system is refused with 403; on a work item, its engagement through `authorise`), then answers 404 with the flag off and 501 `not_implemented` with it on until its task lands, so no principal learns the flag state it may not use (DEC-261). A work item outside the tenant, behind a wall or not of kind `assurance` answers 404 (INV-3). Client roles hold no cell on the three record actions.

## 3. Models
Classification per field (ADR-031): **C** confidential, everything else internal; nothing Restricted, no TIN, no amount, no materiality.

- **`AuditIndexPage`** = the P-36 envelope of `AuditIndexRowOut` + `summary` (`AuditIndexSummaryOut`: `ebp`, `fs_audit`, `review`, `compilation_preparation`, `soc`, `internal_audit`, the caption). `counts` per `audit_engagement` phase code **minus the active tile**; `facets.segment` (registered and entitled segments only), `facets.type`, `facets.partner`, `facets.office`, `facets.period`. No hidden-count field.
- **`AuditIndexRowOut`**: `work_item_id`, `engagement_id`, `client_id`, `client_name` C, `name` C, `engagement_type` (attest types; no `single_audit`), `segment` (`fs`, `ebp`, `review`, `soc`, `ia`), `ebp_plan_kind` (`dc`, `403b`, `db`), `limited_scope_103a3c`, `is_group_audit`, `period_label` C, `phase` (C2 `audit_engagement`), `released_on`, `run_badge` (`AuditRunBadgeOut`: `run_id`, `run_number`, `started_at`, `started_by_user_id`, `started_by_name`, `workpapers_complete`, `workpapers_total`, `blocked_on_role`; C6 engagement runs only, DV-11), `tags` C (`AuditIndexTagOut`: `source`, `code`, `text` C, `classification`), `pbc` (`AuditPbcOut`: `received`, `total`; null before G3, DEC-39), `partner_initials`, `manager_initials`, `office_id`, `office_name`, `report_due_on` (`work_items.due_on`, DV-6), `report_due_tone` (`past_due`, `within_7_days`, `within_30_days`, `later`; from `kernel.clock`), `archive` (`AuditArchiveOut`: `state` `archiving`\|`archived`, `days_left`, `firm_tool_ref` C), `allowed_actions`.
- **`AuditCockpitOut`**: `work_item_id`, `engagement_id`, `audit_bar` C (`AuditBarOut`: `title` C, `methodology_label`, `run_started_at`, `auto_mode` null without the `engagement_run.auto_mode` capability), `overview` C (`AuditOverviewOut`: `client_id`, `client_name` C, `name` C, `period_label` C, `phase`), `bands` C (`AuditBandOut`: `key` `overview`\|`planning`\|`group`\|`fieldwork`\|`completion`\|`reporting`, `collapsed`, `rows`), `dock_tabs` (`agent`, `viewer`), `phase_mode` (`recorded`\|`derived`), `read_only_reason` (`archived`), `version`, `allowed_actions`.
- **`AuditSectionRowOut`**: `key`, `title`, `work_item_ref`, `section_state` (C2 `audit_section`; null on an Overview link row), `grammar` (`sub_line`\|`idle_pill`\|`link`), `sub_line` C (code-built text), `route` (manifest screen ID), `link` (`live`\|`planned`; planned renders as text without a chevron, DV-1), `blocked_on_user_id`, `blocked_on_name`, `allowed_actions`.
- **`AuditProfileIn`** `{ebp_plan_kind?, limited_scope_103a3c?, standards_set_id?, seen_version}` (extra fields refused) → **`AuditProfileOut`** `{work_item_id, ebp_plan_kind, limited_scope_103a3c, standards_set_id, version}`.
- **`AuditPhaseIn`** `{to (C2 audit_engagement), reason? C ≤ 300}` → **`AuditPhaseOut`** `{work_item_id, event_id, from_phase, to_phase, mode, recorded_at, version}`.
- **`ReleaseRecordIn`** `{report_released_on, report_kind (opinion\|no_report)}` → **`ReleaseRecordOut`** `{work_item_id, report_released_on, report_kind, phase, archive_due_on (+60 days), recorded_at}`.
- **`ArchiveRecordIn`** `{export_id, firm_tool_ref C ≤ 120}` → **`ArchiveRecordOut`** `{work_item_id, export_id, manifest_sha256, phase, recorded_at}`.
- **`SourceDocumentsOut`**: `work_item_id`, `received`, `total`, `needs_review`, `requested`, `groups` C (`SourceDocumentGroupOut`: `category_id`, `label` C, `received`, `total`, `counted` (false for "Sample-driven"), `rows`). **`SourceDocumentRowOut`**: `request_item_id`, `binder_id`, `title` C, `status` (C2 `request`), `overdue` (derived), `requested_at`, `due_on`, `owed_by` (`RequestOwedByOut`: `kind` `client_contact`\|`third_party`\|`organisation`, `display` C), `latest_upload` (`RequestLatestUploadOut`: `evidence_version_id`, `path_label` C, `uploaded_on`, `uploader_kind` `client`\|`third_party`\|`firm`\|`connection`), `match_confidence` (0–100), `linked_count`, `screening` (C2 `evidence_screening`), `returned_reason`, `allowed_actions`.

**C5 v1.1 (additive, in place):** P-06's `BinderRequestRowOut` (`GET /v1/binders/{id}/requests`) gains `owed_by`, `latest_upload` and `match_confidence`, all optional and null until A-01-T10 populates them, and **firm-only**: a client principal's rows never carry them (`requests.contract.for_viewer`); `requested_at`, `overdue`, `screening` and `linked_count` already exist and serve AUD-03 as they are. P-06's consumer tests stay green.

## 4. Status words
From `docs/product/status-vocabulary.yaml`: `audit_engagement` (planning, fieldwork, in_review, completion, ready_to_release, released, archiving, archived; `processing` derived), `audit_section` (the rail's sub-line and idle-pill words), `request` (DEC-09, `overdue` derived), `evidence_screening` (passed, flagged, not_screened), and `engagement_export` (queued, packaging, ready, failed, expired, undone) for the export sheet (A-01-T17).

## 5. Human-only actions
`assurance.record_phase`, `assurance.record_release` and `assurance.record_archive`: the matrix denies `agent` and `system` and grants no client role; the services require a live human (`require_live_human`); `assurance_phase_events` (A-01-T05) has `CHECK (mode <> 'recorded' OR actor_kind = 'human')`, binds each row's actor to the session's (`app.actor_kind`, `app.actor_id`), refuses backward and multi-step recorded moves in its SECURITY DEFINER insert trigger, and is the only way the phase moves (the app role cannot update `phase`); `assurance.phase_recorded` is on the human-only register (0135); and the release and archive tables (A-01-T23) `actor_kind = 'human'`. These join chapter 06's I-AGENT-NEVER list in A-01-T25. The cockpit never renders Run, Begin…, Sign off run or Auto mode without the capability in `allowed_actions` / `/v1/me`.

## 6. Errors
| Status | Code | When |
|---|---|---|
| 404 | `not_found` | flag off; work item outside the tenant, walled, or not assurance |
| 403 | `forbidden` | role, independence, an agent or system context (a plain 403); on release and archive a stale second factor answers `facts.reason = mfa_required` and nothing else does (DEC-592) |
| 403 | `archived_write` | a write on an archived work item |
| 409 | `phase_backward` | the target phase is the current one or before it |
| 409 | `phase_skip` | the target is beyond the next record-mode phase |
| 409 | `phase_follows_gate` | the target phase's gate has a registered provider: it derives from `gate.met` |
| 409 | `stale_version` | PATCH profile with an old `seen_version` |
| 422 | `phase_invalid` | a phase reason over 300 characters |
| 422 | validation | PATCH profile with `limited_scope_103a3c: null`, or a body that changes nothing |
| 409 | `release_mode_in_app` | release record while the firm's `assurance_release_mode` is `in_app` (A-01-T23) |
| 409 | `final_export_required`, `export_stale` | archive record without a ready, current final binder export (A-01-T23) |
| 422 | `release_date_future` | release date after `clock.today()` (A-01-T23) |
| 409 | `record_out_of_phase` | a release record before In review or once released; an archive record before Released (A-01-T23, DEC-590; `facts.phase`) |
| 501 | `not_implemented` | flag on, task not landed |

Bodies are `{"detail": ..., "code": ..., "facts": {...}}` with identifier-only facts.

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| audit `assurance.profile_updated` | PATCH profile | work item, changed field names |
| audit `assurance.phase_recorded` | a person records a phase | work item, from, to, mode `recorded` |
| audit `assurance.phase_derived` | a registered gate's `gate.met` moves the phase | work item, from, to, gate |
| audit `assurance.release_recorded` | external release (A-01-T23; human-only register) | work item, date (`YYYYMMDD`), `no_report`, `mfa_at` (epoch) |
| audit `assurance.archive_recorded` | external archive (A-01-T23; human-only register) | work item, export ID, manifest SHA-256, `as_of_seq`, `engagement_archived`, `mfa_at`; never the firm-tool reference |
| outbox `assurance.phase_changed` | every phase move | engagement, work item, from, to, mode |
| outbox `gate.met` | consumed (C1) | engagement, gate |

## 8. Example payloads
Brightwater Hale (synthetic) only: the AUD-01 a index foots 7 + 9 + 6 + 2 + 3 = 27 with caption EBP 14 · FS audit 6 · Review 4 · Compilation/preparation 3; Northwind's row reads PBC 11 of 24, MO / HL, Chicago, report due Oct 9; Bayside's `archive` is `{state: archiving, days_left: 13}` on Sep 14; Source Documents for Northwind foots 24 = 11 + 1 + 12 with groups 3/5 · 4/6 · 3/7 · 1/4 · 0/1 · 0/1. The fixture payloads are `apps/web/src/fixtures/seed/audits-index.ts` (A-01-T03) and the screens' scenarios.

## 9. Consumer contract tests
`backend/tests/contracts/audits/test_audits_stub.py` (A-01-T02: routes, actions, 404/501, idempotency, classification, human-only), `backend/tests/contracts/audits/test_audits_consumers.py` (A-01-T03: envelope, registry codes, no hidden counts, C5 v1.1 fields), `apps/web/src/fixtures/contracts/audits.contract.test.ts` (A-01-T03: AUD-01, AUD-02 and AUD-03 fixture shapes and footings).

## 10. Registration slots (`assurance.api`)
| Slot | Signature | Rule |
|---|---|---|
| `register_audit_section` | `(key, band, order, route, state_provider, *, title="", link="planned", required_action=None, action_scope="engagement")` (additive, DEC-312: the cockpit checks `required_action` for the reader, on the engagement or the firm, before asking the provider) | the provider answers `SectionState(state, grammar, sub_line, blocked_on_user_id)` or `None` (row left out); no provider → refused; a taken key refuses a different registration |
| `register_index_tag` | `(name, provider, classification)` | `metadata` tags reach metadata-only roles; `content` tags do not (ADR-024) |
| `register_audit_segment` | `(family, entitlement)` | A-01 registers `fs`, `ebp`, `review`; X-01 `soc`, X-03 `ia` with their entitlements |
| `register_run_summary` | `(provider)`: `(tenant, work_item_ids) -> {work_item_id: RunSummary}` | P-10's C6 v1 engagement runs; none registered, or a failing provider, means no "Processing" and no "Started …" (DV-11, DEC-312) |

A-01's own registrations (DEC-312): Overview rows `client`, `methodology`, `standards_set`, `source_documents`, `team`, `activity`; metadata tags `letter_sent`, `eqr`, `no_report`. C5 v1.1 facts are filled by `requests.source_documents` with evidence's `register_upload_facts` provider (DEC-313).

## 11. Versioning
| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | — | — | stub 2026-10-24 (A-01-T02); C5 v1.1 additive fields in place; profile and phase live (A-01-T05, DEC-262: phase-to-gate map, `phase_invalid` 422 for a reason over 300 characters); index, cockpit and Source Documents live 2026-10-25 (A-01-T08 to T10, DEC-311 to DEC-313; the cockpit's action is `engagement.read_metadata`, the C5 v1.1 fields filled); release and archive records live 2026-10-27 (A-01-T23, DEC-590 to DEC-592) |

## 12. Open points
- DEC-261: slot shapes, the `engagement.read_metadata` index refusing portal principals in the route, and the C5 v1.1 fields as optional.
- Decided (DEC-590): one G8 and one G9 provider stay registered for every firm, each met by SPEC-314's in-app act or by the record-mode record; `assurance_release_mode` (typed firm setting, `external` default) decides which write is open. A record archive sets `work_items.archived_at`, never `archive_locked_at` (DEC-591). The AUD-01 row reads the recorded release date and, for a content reader, the firm-tool reference of an external archive.
