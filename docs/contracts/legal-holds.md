# Legal holds (v1)

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md` (the legal-hold part of Q-02's compliance kernel) |
| Version | v1 |
| Status | live behind `compliance.legal_holds` (Q-02-T29, 2026-10-24) |
| Provider epic | Q-02 (`evidence`) |
| Consumers | FIL-02 b and h (Q-05), ADM-06, P-06-T19 (withdrawal purge), Q-05 (destruction), G-02 |
| Freeze sprint | the sprint review after this change |
| Flag | `compliance.legal_holds` (off: the three routes answer 404). The hold check, inheritance and the workflows are never flagged |
| Spec | Q-02 §3.8 (AC-34 to AC-37), §4.2, §4.3, §4.5 (`docs/plan/epics/Q-02.md`) |
| ADRs | ADR-033, ADR-162, ADR-017, ADR-090; DEC-71 / P-14; DEC-227, DEC-228 |

## 1. Purpose
A person preserves a client, a client and tax year, an engagement or a work item. While any hold covers a stored evidence version, nothing may erase it (retention expiry, a client's withdrawal, a destruction batch), and S3 holds the object with an object legal hold. Holds are reference-counted: lifting one leaves every object another hold still covers held.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| List holds (metadata and counts) | `GET /v1/legal-holds` | `legal_hold.read` | firm admin, security admin, partner-level members (`firm_partner`), quality partner; walled clients absent | denied |
| Place a hold | `POST /v1/legal-holds` → 202 | `legal_hold.place` (fresh MFA) | firm admin, security admin, partner-level members (C-10) | denied |
| Lift a hold | `POST /v1/legal-holds/{id}/release` → 202 | `legal_hold.lift` (fresh MFA) | the same | denied |

Placing and lifting are authorised on the scope's client, so an ethical wall refuses them.

## 3. Models
Code: `backend/src/abacus/modules/evidence/hold_routes.py`.
- **`LegalHoldIn`**: `scope` (`kind`: `client` · `client_tax_year` · `engagement` · `work_item`, with `client_id`, `tax_year` (1990 to 2100), `engagement_id` or `work_item_id` as the kind needs), `reason_code` (`irs_examination`, `litigation`, `regulatory_inquiry`, `subpoena`, `other`), `details` (optional, at most 2,000 characters, Confidential, never returned), `notify_user_ids` (at most 50, firm staff only).
- **`LegalHoldReleaseIn`**: `reason` (one line, at most 500, Confidential, never returned).
- **`LegalHoldOut`**: `id`, `scope_kind`, `client_id`, `tax_year`, `engagement_id`, `work_item_id`, `reason_code`, `status`, `placed_by`, `placed_at`, `released_by`, `released_at`, `objects_held` (versions the hold still counts), `objects_applied` (of those, with the S3 hold confirmed). `LegalHoldsOut` is `{items: [...]}`, newest first.

**Scope semantics (DEC-228).** A tax year covers every engagement of the client whose fiscal period, or any of whose work items' periods, overlaps that calendar year. A work item covers its whole engagement, because evidence versions don't name a work item yet. Archived engagements are included.

## 4. Status words
`legal_hold` (status vocabulary): Applying · Active · Releasing · Released. Forward only. A hold can be lifted only while Active.

## 5. Human-only actions
`legal_hold.place` and `legal_hold.lift` deny `agent` and `system`; the table binds `placed_by` and `released_by` to the session's own person; `legal_hold.placed` and `legal_hold.lifted` are in the human-only register, so the database refuses them from an agent or policy actor.

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not found"}` | flag off; a scope or hold outside the firm |
| 409 | `{"detail": "hold_not_active"}` | lifting a hold still applying, or already lifted |
| 422 | `{"detail": "notify_not_member"}` | someone on the notify list isn't current firm staff |
| 403 | `{"detail": "forbidden"}` | no action, a wall, or stale MFA |

## 7. Audit, outbox and notifications
| Event | Actor | When |
|---|---|---|
| `legal_hold.placed` | the person | placed; every version in scope is counted in the same transaction |
| `legal_hold.counted` | system | the apply workflow found versions created while the hold was placed |
| `legal_hold.applied` | system | S3 holds set on a batch (count) |
| `legal_hold.activated` | system | every version in scope is held in S3 |
| `legal_hold.inherited` | the uploader's transaction | a new version was counted under the holds covering it |
| `legal_hold.lifted` | the person | lifted |
| `legal_hold.released` | system | a batch let go (count; how many S3 holds came off) |
| `legal_hold.ended` | system | released |

Outbox: `legal_hold.placed` (starts `LegalHoldApply` and notifies `legal_hold_placed`: the notify list and the partners of the engagements in scope, firm staff not walled from the client, never the placer) and `legal_hold.lifted` (starts `LegalHoldRelease`). Email text is database rows.

## 8. Internal APIs (no HTTP)
- `kernel.holds.held_versions(tenant, version_ids)` and `erasable_versions(...)`: the fail-closed hold-check slot. Evidence registers `holds_covering`; with nothing registered both raise `HoldCheckMissing` and the caller erases nothing. P-06's purge and Q-05's destruction call it.
- `evidence.api.holds_covering(tenant, version_ids)`: an unreleased hold object, or an open hold whose scope contains the version (a version written while the hold was being placed); a version the firm doesn't have counts as held.
- Workflows: `LegalHoldApply` (`legal_hold_apply:<tenant>:<hold>`) and `LegalHoldRelease` (`legal_hold_release:<tenant>:<hold>`), batch class, 200 versions per step, unlimited retries.

## 9. Consumer contract tests
`backend/tests/integration/test_legal_holds.py` (AC-34 to AC-37, a shared stored object, the list and walls); `backend/tests/unit/kernel/test_holds.py` (fail closed); `backend/tests/workflows/test_legal_holds_replay.py`.

## 10. Versioning
| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | | | live 2026-10-24 (Q-02-T29) |
