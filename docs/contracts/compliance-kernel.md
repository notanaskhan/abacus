# Compliance kernel (v1.3)

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md` |
| Version | v1.3 (Q-02-T43: the firm export is live; the link is an API path the signed-in person opens, §2, §3; DEC-509). v1.2 (Q-02-T04: the kernel slots, their consumers and how each fails closed, §8). v1.1 (Q-02-T38): the firm-export stub joins the live incident, retention and hold halves |
| Status | live (firm export, Q-02-T43, 2026-10-27; stub since Q-02-T38); live halves as listed in §1 |
| Provider epic | Q-02 (`evidence`, `platform`) |
| Consumers | Every epic in §8 (P-03, P-04, P-06, G-02, A-01, T-01, K-02, P-09, P-10, A-07, Q-05). For the screen family: G-02 (ADM-06 a to h: G-02-T11 stub, T12 suite, T16 screen, T18 incidents, T19 schedule), Q-02-T43 (implements the export), Q-02-T46 (independent ACs), Q-05 (FIL-02 reads of policies and holds) |
| Freeze sprint | S9 (the sprint G-02 consumes it); Q-02-T43 makes the export live behind it |
| Flag | `compliance.firm_export` (export routes; off: 404), `compliance.incidents`, `compliance.legal_holds` |
| Spec | `docs/specs/SPEC-341-compliance-kernel-real-data-readiness.md` (AC-1 to AC-46, the epic's numbers); Q-02 §3, §4.2, §4.3, §8 (`docs/plan/epics/Q-02.md`) |
| ADRs | ADR-097, ADR-004, ADR-031, ADR-139; DEC-71 / P-14, DEC-72 (conflict C-11), DEC-227, DEC-290 |

## 1. Purpose
One index for what G-02's security center and Q-05's records screens build on: the incident register with its FTC clock, retention policies, legal holds, and the dual-approval firm export. Each half keeps its own contract file; this file fixes the firm-export stub and the versions consumers test against.

| Half | Contract | Version | State |
|---|---|---|---|
| Incident create with the clock (`ftc_notify_by`, `clock_day`, `clock_days`, `notification_event`) | `security-incidents.md` | v0.1 | live behind `compliance.incidents` (Q-02-T33) |
| Retention policies read and save | `retention.md` | v1 | live (Q-02-T23) |
| Legal holds read, place and lift | `legal-holds.md` | v1 | live behind `compliance.legal_holds` (Q-02-T29) |
| Firm export request, approve, decline, link, archive and list | this file §2 to §7 | v1.3 | live behind `compliance.firm_export` (Q-02-T43) |

## 2. Who may call it (firm export)
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| List the last 12 exports | `GET /v1/firm/data-exports` | `firm_export.read` | firm admin, security admin, partner-level members | denied |
| Request an export | `POST /v1/firm/data-exports` → 202 (`Idempotency-Key`) | `firm_export.request` (fresh MFA) | security admin | denied |
| Approve | `POST /v1/firm/data-exports/{export_id}/approve` | `firm_export.approve` (fresh MFA) | the named approver: security admin or partner level, never the requester | denied |
| Decline | `POST /v1/firm/data-exports/{export_id}/decline` | `firm_export.approve` (fresh MFA) | the named approver | denied |
| A download link | `POST /v1/firm/data-exports/{export_id}/link` | `firm_export.download` (fresh MFA, not offshore) | the requester or the approver | denied |
| The archive (the link) | `GET /v1/firm/data-exports/{export_id}/links/{link_id}` (one `Range`, 206; `application/zip`, `no-store`) | `firm_export.download` (fresh MFA, not offshore) | the person the link was issued to, still the requester or the approver | denied |

A link is not a presigned URL (ADR-104, DEC-509): it is the archive route's path, which opens only for the signed-in person it was issued to, re-authorised when opened and before each segment of the stream. The archive is stored sealed under the tenant's key in segments (`exports/<tenant>/firm-<export_id>/`). At most 20 links per person an hour, 60 archive requests per person a minute and two open streams per person (429 `download_rate_limited`). A failed build's segments are deleted. Audit rows never carry a link's id (DEC-511).

## 3. Models
Code: `backend/src/abacus/modules/evidence/firm_export_contract.py`. Internal unless stated.
- **`FirmExportRequestIn`** `{approver_user_id, scope = "all"}` (extras refused). v1 exports everything (ADM-06 b "Export all firm data?").
- **`FirmExportDeclineIn`** `{reason?}` (one line, at most 500, Confidential).
- **`FirmExportOut`** `{id, status, scope, origin (on_demand · scheduled), requested_by {user_id, display_name (Confidential)}, requested_at, approver {…}, decided_at?, ready_at?, available_until? (the 7-day window), size_bytes?, manifest_sha256?}`.
- **`FirmExportPageOut`** `{items}` (at most 12, newest first).
- **`FirmExportLinkOut`** `{url (Restricted, never logged: the archive route's path), expires_at (15 minutes, never past `available_until`), manifest_sha256}`.
- **The archive** (DEC-508; Q-02-T47, DEC-640): a ZIP with `index.json` (format `0.2`: export, firm, requester, approver, when built; `packages`, one A-01 engagement export package (format v1, `engagement-export-v1.md`) per engagement the approver may read, each `{engagement_id, work_item_id, path, bundle_sha256, manifest_sha256, bytes, file_count, request_count}` and stored as is at `packages/<engagement_id>.zip`; and `omitted`, every other engagement of the firm with its reason, `not_readable` (a wall, a role or independence), `not_an_audit` (no assurance work item), `no_binders` (no asked PBC binder) or `unsafe_contents`), the packages, and `manifest.json` (every other file's path, bytes and SHA-256; a package's is its stored bytes'). `manifest_sha256` is the SHA-256 of `manifest.json`. A package is built as the approver may read the engagement (INV-5), from every asked PBC binder of its assurance work item, accepted and unaccepted versions, without the audit-trail section; a file whose bytes no longer match its fingerprint fails the export (RB-29).

## 4. Status codes and errors
`status`: `awaiting_approval` → `building` → `ready` → `downloaded` · `expired` (the window ends) · `declined` · `failed`. These are the contract's codes; the words ("Waiting for approval · Margaret Okonkwo", "Scheduled") are G-02's screen copy, registered in the status vocabulary when G-02-T11 adds the card.

| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not found"}` | flag off; an export of another firm or none |
| 422 | `approver_invalid` | the approver is the requester, or no security admin or partner-level member |
| 409 | `approver_must_differ` · `export_not_awaiting_approval` · `export_not_ready` · `requester_not_active` | the requester decides; a decided export; a link before the archive is built; an approval once the requester is no longer an active security admin |
| 403 | `forbidden` (`facts.reason = mfa_required` for a stale second factor) | not the named approver; not the requester or approver for a link; a role refusal |
| 410 | `export_expired` · `link_expired` | a link or the archive after the 7 days (either clock); the archive after its link's 15 minutes |
| 416 | `range_not_satisfiable` (`Content-Range: bytes */size`) | the archive with a range it does not serve (DEC-536's rules) |
| 429 | `download_rate_limited` | more than 20 links an hour, more than 60 archive requests a minute (each recorded in `firm_export_downloads`), or a third open stream |

## 5. Human-only actions
`firm_export.request`, `firm_export.approve` and `firm_export.download` deny the agent and system at the matrix; `firm_export.approved` is on the human-only register (Q-02 AC-17). Two distinct people are needed (DEC-72): the service refuses the requester as approver, and the database refuses it again (Q-02-T43, migration 0216): a CHECK keeps `approver_id` and `requested_by` apart, the insert trigger binds the request to the acting security admin and checks the approver's membership, and the guard lets only the named approver, as the session's person, decide.

## 6. Fixtures (seed-derived)
`apps/web/src/fixtures/seed/compliance.ts` and `handlers/compliance.ts` (fixture mode), mirrored by `backend/tests/contracts/compliance_kernel/`: INC-2026-005 "Credential-stuffing attempts against client portal sign-in", discovered Thu Sep 10, 2026 2:14 AM CT, 0 confirmed, Day 4 of 30 and notify by Sat Oct 10 at E0 (Mon Sep 14, 2026, 9:24 AM CT); the monthly history Sep 1 386 GB, Aug 1 371 GB, Jul 1 359 GB (each at 2:00 AM CT, its 7 days over by E0, so `expired`); Felix Andersen's request "Waiting for approval · Margaret Okonkwo". The incident timeline, two-person decisions and the schedule are G-02's (G-02-T18, T19).

## 7. Audit and outbox (Q-02-T43)
`firm_export.requested`, `firm_export.approved`, `firm_export.declined`, `firm_export.ready` (system), `firm_export.failed` (system), `firm_export.expired` (system, the daily `export_expiry:platform` sweep), `firm_export.downloaded` (each link issued), `firm_export.streamed` (each archive request, with bytes and range); outbox `firm_export.approved` starts `FirmExportWorkflow` (`firm_export:<tenant>:<id>`), `firm_export.expired` deletes the segments; notifications `firm_export_approval_requested` (the named approver) and `firm_export_ready` (requester and approver). Identifiers only.

## 8. Kernel slots: consumers, sprint and fail-closed behaviour (v1.2, Q-02-T04)
The internal interfaces the rest of the product builds on. "Sprint" is when the consumer first needs the slot (epic Q-02 §8.4; chapter 01 calendar). "State" is on `origin/main` at `9d7826d7`; SPEC-341 holds the AC-level detail. A slot that cannot answer never answers "allowed": each row says what happens instead.

| Slot | Interface | Consumers (sprint) | State | Fails closed how |
|---|---|---|---|---|
| Classification flags | `kernel.classification.classified(level, *, tri, phi, pii_kind)`, `tri_paths`, `phi_paths`, `pii_paths`, `mask(value, kind)` | P-03 (S8: masked material, reveals), T-01 (S16: TRI gate), every module's models | built (ADR-167, DEC-295) | A flag on a non-Restricted field fails at import; an untagged value is treated as Restricted by the scrubber; a valid TIN pattern in model context refuses the call (`pii_in_context`) before any network call |
| Data boundary facts | `ai_gateway` boundary registrations (`register_client_data_facts`); opt-in, exclusion and stage reads | P-04 (S6: SHL-10 flip), G-02 (S12: ADM-04), P-10 (S29), P-09 (S31), Q-04 (S12) | partial (SPEC-036; Q-02-T08 open) | A missing fact, register entry, opt-in, stage or a set exclusion refuses with its reason (`route`, `terms`, `firm`, `agent`, `stage`, `engagement`), audited, never retried or rerouted |
| Attribution | `tx.record(action, target=, scope=Scope(engagement_id, work_item_id))`; `on_behalf_of` from the context; `app.on_behalf_of` | P-04 (S6), G-02 (S9: ADM-07), A-01 (S11), every module | built | The database refuses an agent row without its person and a person that is not the transaction's; a `policy` row without `policy_ref` |
| Human-only guard | `docs/architecture/human-only-actions.yaml` → `abacus_human_only_actions()` | P-04 (S6), every epic that adds a human decision | built | A listed action inserted with actor `agent` or `policy` raises before commit, whatever the matrix says |
| Access events | `kernel.access.register_access_kind(kind, flags)`, `record_reads(tenant, kind, subjects)` | P-03 (S8: reveals, renditions), T-01 (S16: `taxpayer_contact_id`, `tax_year`), G-02 (S12), Q-02-T43 (downloads) | built (partitions by hand until schedules) | An unregistered kind raises `UnknownAccessKind`; a failed write means the content is not served (the row is written before content is handed over) |
| Hash chain | `audit_trail.api.latest_checkpoint(tenant)`, `verify_chain(tenant)`; `evidence.api.anchor_chain` | G-02 (S12: export manifests), A-07 (S27+: the seal), Q-03 (restore drill) | partial (schedules not built) | A mismatch reports the first broken checkpoint and raises `abacus.audit_chain.mismatch` (SEV1); a late commit is reported apart; `latest_checkpoint` returns none rather than an unsealed root |
| Retention | `evidence.api.retain_until_for`, `extend_retention_for`; `RECORD_TYPES`; `GET`/`PUT /v1/retention/policies` | G-02 (S12: ADM-06 h), T-01 (S16: 8879 and consent floors), K-02 (S16: drift test), A-07 (S27+), Q-05 (S50) | built (clock schedule not built) | No published floor or policy: retain-until falls back to `evidence_retention_days`, never a literal; a policy below its floor answers 422 `below_floor`; extension only ever extends |
| Hold check | `kernel.holds.erasable_versions(tenant, ids)`, `held_versions`; `evidence.api.holds_covering` registered at import | P-06 (S7: withdrawal purge), Q-05 (S50: destruction), access-event partition drops | built | No registered check raises `HoldCheckMissing` and the caller erases nothing; a hold still `applying` already counts its versions |
| Incident clock | `platform.api.incident_clock(discovered_at, zone)`; `POST /v1/firm/security/incidents` | G-02 (S11 to S12: ADM-06 a, d; T18 timeline) | built | A discovery in the future is refused; unknown counts are "not (yet) a notification event", never an assumed one; flag off answers 404 |
| Firm export | §2 to §7 of this file | G-02 (S12: ADM-06 b, f, g), A-01 (S11: package reuse) | live (Q-02-T43); per-engagement packages Q-02-T47 | Flag off 404; the requester is never the approver (service and database); a link answers 410 after the 7 days on either clock |
| Fresh MFA list | `docs/architecture/fresh-mfa-actions.yaml` | every epic adding a listed action; P-08 (S7: portal floor) | built (lint); staff `amr` refusal and `make mfa-report` not built | A listed action without `mfa_recent: required` fails CI; a stale factor answers 401 `mfa_required` |
| Run records | `agents.api.run_record(run_id)`; C6 v1 stub (ADR-169) | A-01 (S11), G-02 (S12), A-07 (S27+), P-09 (S31) | not built (Q-02-T41, T45) | Until built, consumers read C6 v0 (`docs/contracts/agent-runs.md`); walled runs answer 404 |

**Leaf version rule.** A change that adds a column to `audit_events` bumps the chain's leaf version in the same PR (epic R7); the canonicaliser lists every column it covers. Leaf version 2 (G-02-T06, migration 0172, 2026-10-26) adds `ip`, `user_agent_family`, `device_label`, `session_id`, `auth_method`, `mfa_at`, `client_id` and `office_id`; checkpoints sealed at version 1 keep verifying with version 1's columns.

## 9. Changelog
- v1.3 (2026-10-27, Q-02-T43, TASK-1403): the firm export is live; the archive route `GET …/links/{link_id}` (the link's `url`), 403, 410 `link_expired`, 416, 429; the archive's v1 skeleton (DEC-508, DEC-509).
- v1.2 (2026-10-25, Q-02-T04, TASK-1239): §8 kernel slots; spec link to SPEC-341.
- v1.1 (2026-10-25, Q-02-T38, TASK-1201): firm-export stub; index of the incident, retention and hold halves.
