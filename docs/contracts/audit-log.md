# Audit log (v1)

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md` (G-02) |
| Version | v1 |
| Status | stub (G-02-T04, 2026-10-26): every route answers 501 with the flag on |
| Provider epic | G-02 (`audit_trail`; slots in `platform`; capture in `kernel.uow`) |
| Consumers | ADM-07 (G-02-T13); the F-04 harness (`since_seq`, INV-5 on staging); A-01 (`events_for_work_item`); P-05 (AUD-29); P-09 (Run links) |
| Freeze sprint | the sprint review after the stub |
| Flag | `audit_log.explorer` (default off, created 2026-10-26, expires 2027-04-21 under DEC-137); `audit_log.values` for read-time values (G-02-T09) |
| Spec | SPEC-349 (AC-1 to AC-14, AC-45 to AC-47); G-02 §4.3 |
| ADRs | ADR-007, ADR-024, ADR-026, ADR-031, ADR-139 (P-36), ADR-159 (P-43), ADR-187 (P-08); DEC-43, DEC-60, DEC-415 |

## 1. Purpose
One firm-wide, immutable, filterable log of every event, read by the people who answer for the firm: who did it (a person, a person via Agent, a named policy, the system or a support engineer), to what, from where, through which run, and, for a viewer allowed to see them, the values before and after. Nothing here writes an event; corrections are new events.

**Stub behaviour.** With `audit_log.explorer` off every route below answers 404. With it on, every route answers 501 `not_implemented` until G-02-T08 (list, detail) and G-02-T17 (export) land. The legacy SPEC-304 explorer (`GET /v1/firm/audit-events`, `/facets`, `audit.read`) is unchanged until ADM-07 replaces it (SPEC-349 §21).

## 2. Who may call it
| Operation | Method and path | Matrix action |
|---|---|---|
| List | `GET /v1/audit-events` | `audit_event.read` |
| Detail | `GET /v1/audit-events/{seq}` | `audit_event.read` |
| Request an export | `POST /v1/audit-events/exports` (`Idempotency-Key`, 202) | `audit_event.export` (fresh MFA) |
| Export status | `GET /v1/audit-events/exports/{export_id}` | `audit_export.read` (no fresh MFA: a status read; security review L5) |
| Download link | `POST /v1/audit-events/exports/{export_id}/link` | `audit_event.export` (fresh MFA) |

`audit_event.read`: engagement partners and managers, `quality_partner` and `practice_leader` in scope, `firm_admin`, `security_admin`, platform support (SPEC-012). `audit_event.export` and `audit_export.read`: `security_admin`, `quality_partner` and `practice_leader` in scope. The agent and the system are denied all three; client principals get 404 on every route (INV-4, AC-46). No route updates or deletes an event (AC-8).

**The matrix answers first** (security review L1): every route, the stubs included, checks the principal before it reads `audit_log.explorer`: a client principal gets 404, and the agent, the system and anyone refused an export action at the firm get 403, whatever the flag's state. A person's list or detail read is narrowed per event by `visible()` (engagement roles, `in_scope`), so a person with no right sees an empty list. In-scope exporters (`quality_partner`, `practice_leader`) are refused at the firm by the stub; G-02-T17 scopes their export to the events they can see.

**Request context is for three roles** (DEC-420, security review M2): `ip`, `user_agent_family`, `device_label` and `session` (`session_id`, `auth_method`, `mfa_at`) are shown only to firm_admin, security_admin and quality_partner (`REQUEST_CONTEXT_READERS`). Every other reader, engagement partners, managers, practice leaders and platform support included, gets those fields null. The projection lands in G-02-T08; every one of these fields is nullable in the models.

## 3. Shapes
Models in `backend/src/abacus/modules/audit_trail/audit_log_contract.py`; every field carries its classification.

**Facts are codes and identifiers only** (security review M4): `detail_facts` holds counts, booleans, codes and ids, never a value, an amount or free text, because metadata-only readers (`firm_admin`, `security_admin`) receive it. Anything that carries a value lives under the detail's `values`, resolved per viewer and masked (ADR-024, DEC-60). `labels` maps the ids in a row (people, policies, agents) to the display labels their owners' labelers give, never above Confidential. `q` searches labels only (actor, target and fact labels), never a value, for every reader, so a need-to-know reader cannot probe a value through search.

**Codes and facts, never titles.** A row carries its action code, the activity catalogue's `category` (`decision`, `change`, `access`, `run`, `sign_in`, `communication`, `export`) and `mark` (`ok` a named person's approval or sign-off, never agent output; `no` a reversal or removal; `pl` neutral), the actor's facts and the target's identifiers. The SPA composes the title ("Report prepared by Hannah Leclerc via Agent") and the detail line from `action` and `detail_facts` through its copy registry.

- **`AuditEventRow`**: `seq`, `effective_at` (business time, F-04-T06), `action`, `category`, `mark`, `actor` (`AuditActorOut`), `target` (`AuditTargetOut`: `type`, `id`, `label` when its owner's labeler names it, `engagement_id`, `client_id`), `detail_facts` (codes and ids), `labels`, `office_id`, `ip`, `run_id`, `link_kind` (`run` or `none`).
- **`AuditActorOut`** (INV-5): `kind` ∈ `person`, `via_agent`, `policy`, `system`, `support`. `person` and `support` carry `person`; `via_agent` carries `on_behalf_of` and `agent_id` (never a display name for the agent); `policy` carries `policy_ref` (dormant, ADR-187: fixture-only); `system` carries nothing. No row can name "Accrued Agent" as an actor.
- **`AuditEventPageOut`**: the P-36 envelope (`items`, `next_cursor`, `total`, `total_capped`, `counts`). `counts` keys: `all`, `person`, `via_agent`, `policy`, `system`, over the other filters, capped like `total` ("4 of 1,962" is `total` 4 with `counts.via_agent` over the date range). Walled events are in no count and nothing says they were left out (DEC-43, AC-4).
- **`AuditEventDetail`** (the row plus): `occurred_at`, `authority` (`code`, `facts`), `device_label`, `user_agent_family`, `session` (`session_id`, `auth_method`, `mfa_at`), `content_hash` (SHA-256 of the event's canonical form, the hash chain's leaf), `values` (`AuditValuesOut`), `source` (`AuditSourceOut`: `run_id`, `agent_id`, `run_no`, `started_at`, `initiator`).
- **`AuditValuesOut`**: `status` `resolved` (with `rows` of `ValueRow`: `item_label`, `field`, `amount` as a decimal string, `before`, `after`, `masked`, and `not_included` of `NotIncludedRow`), `withheld` with `reason` (`need_to_know`: "Values are visible to partners in scope."; `walled`; `not_enabled` while `audit_log.values` is off), or `unavailable` ("Values not available": no resolver, or it failed). A Restricted value only ever appears masked (`•••-••-2208`). No value is stored in `audit_events`, a label row or an export manifest beyond what the requester could see (DEC-60, AC-11).
- **`AuditExportRequestIn`**: `from_date`, `to_date` (the firm's time zone), `filter` (`actor_kind`, `object_type`, `action`, `office_id`), `include_values`. **`AuditExport`**: `id`, `status` (`requested`, `building`, `ready`, `downloaded`, `expired`, `failed`), the request, `requested_by`, `requested_at`, `file_name`, `row_count`, `seq_from`, `seq_to`, `manifest_sha256`, `expires_at`. **`AuditExportLinkOut`**: `url` (Restricted, never logged), `expires_at` (15 minutes), `manifest_sha256`.

Request context (`ip`, `device_label`, `user_agent_family`, `session`) is captured on a person's and a support engineer's events only, and is null on agent and system events (G-02-T06, AC-9). `ip` and `device_label` are personal data (`confidential`).

## 4. Behaviour
- **List** (AC-1, AC-2, AC-6, AC-7): newest first by `seq`; keyset pages that stay stable while new events arrive. Filters: `actor_kind`, `actor_id`, `object_type`, `action`, `from` and `to` (dates on `effective_at`, the firm's time zone), `office_id` (the object's office, else the actor's membership office: DEC-415 Q9), `ip`, `q` (labels through the label index, G-02-T10; never a value), `cursor`, `limit` ≤ 100.
- **`since_seq`** (the F-04 harness): events with `seq` greater than it, **oldest first**, so a consumer can tail the log; combined with the other filters. The harness switches its INV-5 check to this route on staging and the canary (G-02-T21).
- **Visibility** (AC-4, AC-5): through `visible()`: walled events are omitted (404 on detail), with no hidden count. Walls key on `client_id`, which the projection derives from `engagement_id` for history and for new events whose writer left it null, so a null-client row never slips past a wall (security review L4). `firm_admin` and `security_admin` read metadata; values resolve only for a viewer holding the target's content read (`quality_partner` and `practice_leader` in scope, the engagement team).
- **Export** (AC-12 to AC-14): one person with a fresh second factor (DEC-415 Q8). The job writes `audit-log-<from>-<to>.csv`, `manifest.json` (format `accrued.audit-log-export` v1: filter, requester, seq range, row count, the SHA-256 of each file, the P-43 checkpoint covering the range) and `manifest.sig` (the environment's KMS export-signing key) to the exports bucket with a 7-day expiry. Request, ready (system) and download each write an audit event naming the person.

## 5. Module interfaces
- `audit_trail.api.list_events(ctx, filter, cursor, limit)`, `get_event(ctx, seq)`, `events_for_work_item(ctx, work_item_id)` (G-02-T08; A-01 reads the last for the binder export's audit-trail section).
- `platform.api.register_audit_labeler(target_type, labeler)` and `register_audit_value_resolver(target_type, resolver)` (declared G-02-T02, used from G-02-T09): fail closed (no label; `unavailable`), a label above `confidential` is refused.
- Activity catalogue v1 (`audit_trail/activity_catalogue.py`, G-02-T08): each audited action's `category`, `mark` and fact names; modules register theirs through `ACTIVITY_KINDS`, and an action with no entry renders through the generic fallback.

## 6. Errors
404 (flag off, a walled or invisible event, another person's export), 403 (no matrix right; fresh MFA missing on export), 409 `export_not_ready`, 410 `export_expired`, 422 `cursor_invalid` and request validation, 501 while stubbed.

## 7. Change log
- v1 security review (2026-10-26): facts are codes and ids with `labels` beside them (M4); request context for three roles (M2, DEC-420); authorise before the flag (L1); `audit_export.read` for the status read (L5). Still v1: the stub is not frozen.
- v1 (2026-10-26, G-02-T04): stub. Consumer tests `backend/tests/contracts/audit_log/`; fixture mode serves ADM-07 a to g (`apps/web/src/fixtures/scenarios/ADM-07.ts`).
