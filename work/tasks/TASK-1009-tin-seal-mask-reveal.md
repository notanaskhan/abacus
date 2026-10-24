---
id: TASK-1009
title: TIN seal, mask and reveal — organisations.api sealing, masked payloads, the logged reveal, migration 0123 (P-07-T10)
spec: SPEC-321
acceptance_criteria: [AC-9]
risk_zone: red
status: done
epic: P-07
plan_key: P-07-T10
branch: s6-clients-engagements
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"A reveal returns the value once with one audit row and no log line, an offshore member gets 403, and an SSN write on a real tenant answers 422." (P-07-T10; P-07 Story 1.3; DEC-52, DEC-141.)

## Plan (red zone)
- **Migration 0123 `tin_reveals`** (down_revision 0115): insert-only reveal log (entity, engagement whose role allowed it, user, reason code, MFA time), `actor_kind = 'human'` CHECK, immutability trigger. Rollback: `alembic downgrade 0115` (drops the table and its trigger function; synthetic data only).
- **Code:** `organisations/tin.py` *(new)*: `normalise_tin`, `mask_tin`, `seal_tin(tx, entity_id, raw, kind)` (422 `tin_kind_not_allowed` for SSN/ITIN on a non-synthetic firm until C19; 409 `tin_conflict` for a TIN already on file; envelope under the firm's key through `kernel.crypto.seal`, AAD bound to the entity; fingerprint HMAC-SHA256 under a per-firm key derived from a configured pepper), `clear_tin`, `reveal_tin(ctx, entity_id, reason)`. Exported from `organisations.api`.
- **Reveal:** the entity's client must be visible (404 otherwise, walls first); `tin.reveal` is authorised against the client's open engagements one by one (engagement roles; `not_offshore`, `mfa_recent`, reason); 403 when none allows. One unit of work writes the `tin_reveals` row and one `tin.revealed` audit event (target the entity, `after` the reveal id, scope the engagement); a counter `abacus.organisations.tin_reveals` counts by reason only. The value is opened after the audit rows are queued and returned once with `Cache-Control: no-store`; nothing logs it.
- **Record:** CLI-02's `allowed_actions` carries `tin.reveal` when the caller could reveal on one of the client's open engagements (the frontend's `canReveal`). Shapes unchanged.
- **Config:** `tin_fingerprint_pepper` (SecretStr; local and test use a fixed public value; anywhere else unset fails closed, 503).
- **Registry and docs:** `organisations/registry.py` (`tin_reveals` owned, insert-only, insert columns); `error-codes.yaml` (`tin_kind_not_allowed`, `tin_conflict`); `schema_check` expectations; `organisations.yaml` comment; `docs/contracts/clients.md` §reveal; DEC-223.
- **Not in scope (recorded in DEC-223):** ADR-167's `pii_kind` flag on `classified()` is proposed, not accepted, and says not to add the flags yet (Q-02-T32 waits); masking is enforced by the Restricted tag, `MaskedTinOut` and a schema walk test instead. The senior/staff preparer path stays deferred (DEC-141).
- **Tests:** `tests/unit/organisations/test_tin.py` (normalise, mask, fingerprint per firm); `tests/integration/test_tin_reveal.py` (seal, masked record, reveal once with one audit and one reveal row and no log line, offshore 403, no MFA 403, no role 403, walled 404, SSN on a real firm 422, EIN accepted, duplicate 409, plaintext never in the row, outbox or audit); `tests/contracts/clients/test_clients_stub.py` treats the reveal as live.

## Progress log

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-223 | Reveal scope, fingerprint key, pii_kind deferral, reveal log table | No (ADR-167 governs the flags when accepted) |

- 2026-10-24: built as planned. Migration 0123 (`tin_reveals`, down_revision 0115); `organisations/tin.py`; the reveal route live with `no-store`; CLI-02's `allowed_actions` carries `tin.reveal` per open engagement; `tin_fingerprint_pepper` setting. 8 integration tests (`test_tin_reveal.py`) and 4 unit tests pass; clients contract test updated (no stub left). ADR-167's `pii_kind` flag deferred to its acceptance (DEC-223). **Human to-do:** set `ABACUS_TIN_FINGERPRINT_PEPPER` in staging and production secrets before any TIN is sealed there (unset, sealing answers 503). First mistake noted: banned pattern AUTHZ-003 (`archived=False` literal) caught; the archived state now comes from the fact row.

- 2026-10-24: security review fixes (DEC-232), failing tests first: a per-person cap of 20 reveals per rolling hour (429 with `retry_after` and `limit`, audited `tin.reveal_throttled`, warning log, counter); `seal_tin`/`clear_tin` authorise `client.update` on the entity's client after `visible_clients` (walled 404) and take the person's context; `tin_conflict` carries no facts and only the unique index's violation maps to it; stale MFA answers 403 `mfa_step_up_required` instead of a role denial, dead MFA check removed. 11 integration and 5 unit tests pass. Found: identity's `authorise` does not wall `Resource.client` (engagement-less) resources; recorded in DEC-232 as open for identity.
