# C18 · Portal approvals

| Field | Value |
|---|---|
| Register row | C18 in `docs/contracts/README.md` |
| Version | v1 |
| Status | **v1 frozen 2026-11-10 (R-02-T25)**; live (R-02-T11, 2026-11-09, DEC-3009; stub R-02-T03). `proposed_entry` and `fs_draft` are registered; `uncorrected_misstatements` (R-02-T15) and `fs_package` (C-02, A-08) still answer 409. Questions (R-02-T22) answer 501. The entries journal is live (R-02-T14 remainder, 2026-11-10, DEC-3172) |
| Provider epic | R-02 (SPEC-646) |
| Consumers | A-06 (entries, drafts), A-07 (`fs.approved_by_management` and the acknowledgement for release), C-02, A-08 (packages), X-01 (system description, later) |
| Freeze sprint | S30 |
| Flag | `portal.approvals` arrives with R-02-T14 |
| Code | `engagements/client_approvals.py` (slot, decider rule), `portal/approvals.py` (service), `portal/approvals_contract.py` (routes), `adjustments/client_approvals.py` (`proposed_entry`), `reporting/client_approvals.py` (`fs_draft`) |
| Screens | `docs/screens/POR-08.md`, `docs/screens/POR-09.md` a2, b |

## 1. Purpose
One way to put a decision to a client, whatever the kind, and bring it back to the module that owns it.

## 2. The slot
```python
from abacus.modules.engagements.api import register_client_approval_kind

register_client_approval_kind("proposed_entry", provider)  # at module import
```
A provider implements `items(tenant, scope_id)`, `item(tenant, item_id)`,
`decide(tx, item_id, decision, context)` and `facts(tenant, item_id)`. It emits
`client_approval.requested {kind, item_id, scope_kind, scope_id}` when an item is sent and
`client_approval.decided {kind, item_id, decision}` after `decide()`. Its decision row is
`CHECK (actor_kind = 'human')`. The portal lists only items reporting `sent_to_client = true` for a
scope the caller's grant covers. An unknown or unregistered kind: 409
`approval_kind_not_registered`, nothing written (AC-1).

| Kind | Provider (registers with) | Decider (`DECIDER_RULES`; OQ-1, DEC-2400) |
|---|---|---|
| `proposed_entry` | adjustments (R-02-T07) | owner grant or approver of record |
| `uncorrected_misstatements` | assurance (R-02-T15) | owner grant or approver of record |
| `fs_draft` | reporting (R-02-T11) | owner grant or approver of record |
| `fs_package` | closes or attest (C-02, A-08) | owner grant or approver of record; on an attest-flagged client also `ske_designee` |

## 3. Who may call it
Matrix: `docs/architecture/permission-matrix/portal.yaml`. Firm roles, agents, system and support
have no cell. Every read is `scope_only`; out of scope is 404, in scope but not the decider is 403
`not_decider`, no fresh second factor is 401 `mfa_recent_required`.

| Operation | Method and path | Matrix action | Today |
|---|---|---|---|
| Items, counts, contexts | `GET /v1/portal/approvals?scope_id=&context=&filter=` | `client_approval.read` | 501 |
| Detail | `GET /v1/portal/approvals/{kind}/{item_id}` | `client_approval.read` | 409, then 501 |
| Accept or decline an entry | `POST …/proposed-entries/{id}/decide` + `Idempotency-Key` | `proposed_entry.client_decide` | 501 |
| Acknowledge uncorrected | `POST …/uncorrected-misstatements/{item_id}/acknowledge` + `Idempotency-Key` | `uncorrected_misstatements.acknowledge` | 501 |
| Approve or decline a package | `POST …/packages/{id}/decide` + `Idempotency-Key` | `close_package.client_decide` | 409, then 501 |
| Questions | `GET·POST …/{kind}/{item_id}/questions` | `client_approval.ask` | 409, then 501 |
| Entries journal | `GET …/{kind}/{item_id}/journal`: 202 `{render_job_id}` while C11 renders the deterministic `client_entries_journal`, then 302 to `…/journal/file` | `client_approval.read` | 404 (not the person's item), 409 |
| Entries journal file | `GET …/{kind}/{item_id}/journal/file`: the filed PDF (`application/pdf`, `no-store`, attachment) for the admitted person | `client_approval.read` | 404 (not theirs, or not yet filed), 409 |

Management approval of a draft is C10's `POST …/deliverables/{id}/versions/{v}/approve`, decided
through `fs_draft`.

## 4. Rules consumers rely on
- **What you saw is what you decided** (AC-4): a stale `seen_hash` is 409 `item_changed`; the same
  `Idempotency-Key` gives one decision and the original response.
- **Agents never decide** (AC-5): denied at the matrix, the live-human check and the provider's
  CHECK. CLIENT-DECISION-001 names the only files that may call `decide()`.
- **Attribution** (AC-6): every provider receives `ClientDecisionContext`; the row reads
  "Dana Kowalski (client) · Sep 25", never "via Agent".
- **Pack rule** (AC-7): no DTO carries materiality, a threshold, a policy name, a review note, a
  sign-off, the agent, a confidence or an internal status.
- **Decline reasons:** `number_looks_wrong`, `something_missing`, `other` (note required, 1 to
  1,000 characters). Client text is sealed, never HTML, never in an audit row (AC-34).
- **No Post control** exists for an attest client; nothing is written to a client ledger (AC-10).

## 5. The service (R-02-T11)
`portal/approvals.py` composes every registered kind. In order, for a decision:
1. a live client human in a portal session (agent, system, support, firm people: 403 at the
   matrix and again here);
2. the kind's provider (409 `approval_kind_not_registered`);
3. the item, `sent_to_client`, on a scope one of the person's active grants covers (else 404);
4. the decider (`engagements.decider_for`): an owner grant covering the item, or the
   approver-of-record designation of one of the person's contacts on its engagement; for an attest
   client's `fs_package`, also the SKE designee (else 403 `not_decider`);
5. the item still waiting and `seen_hash` current (else 409 `item_changed`, nothing written);
6. once per `Idempotency-Key` (kernel `idempotent`): one unit of work runs the provider's
   `decide(tx, item_id, decision, ClientDecisionContext)` with the person's contact, grant, basis,
   MFA time and portal session, emits `client_approval.decided` and audits
   `client_approval.decided` (identifiers, basis and MFA time).

The list counts waiting, posted, approved and declined before the filter; each item carries the
actions its viewer may take (`accept`/`decline`, `acknowledge` or `approve` for the decider, `ask`
for everyone in scope).

**`proposed_entry`** (adjustments): an entry with a `sent_to_client` decision, waiting while
`approved`, decided by `adjustments.api.apply_client_decision` (an insert-only
`proposed_entry_decisions` row with principal `client_user`, channel `portal` and the client
grant; the status; the owners' hooks; `proposed_entry.client_decided`). Its `seen_hash` covers the
version, amount, description and lines. **`fs_draft`** (reporting): a statement version sent for
approval on the portal channel; approving writes `statement_approvals` (`approved_by_management`,
principal `contact`, channel `portal`, `grant:<id>`), moves the statement and emits
`fs.approved_by_management`. Its `seen_hash` covers the version and its content hash.

## 6. Change log
| Version | Date | Change |
|---|---|---|
| v1 | 2026-11-06 | Stub (R-02-T03, DEC-2403) |
| v1 | 2026-11-09 | Service, decider rule, `proposed_entry` and `fs_draft` providers (R-02-T11, DEC-3009) |

## Freeze (R-02-T25)
C18 v1 is frozen as of 2026-11-10: a new approval kind registers through the provider slot (additive); a change to a request or response shape is v2 with one sprint of overlap.
