---
id: SPEC-321
title: "Clients and engagements v2 (P-07 wave 1): the clients family and the engagements family contracts - outline"
status: draft
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-005, ADR-024, ADR-026, ADR-031, ADR-139, ADR-140]
related_specs: [SPEC-002, SPEC-025]
created: 2026-10-23
updated: 2026-10-23
---

> **Outline.** Written with the clients contract stub (P-07-T04, TASK-434). The epic is the source
> until this spec is final: `docs/plan/epics/P-07.md` §3.1 and §3.6 (stories), §4 (backend), §8
> (contracts). The contracts are `docs/contracts/clients.md` and, from P-07-T05,
> `docs/contracts/engagements-v2.md`. Story 1 holds for the clients stub; Story 2 is the behaviour
> the implementing tasks prove (P-07-T08, T09, T10; P-07-T13 writes the independent suite).

## 1. Summary
A firm finds and opens its clients (CLI-01, CLI-02) on the P-36 list envelope and a record with
`allowed_actions`, behind ethical walls with 404 semantics and no hidden count, with taxpayer IDs
masked everywhere and revealed only by a live, onshore person with recent MFA and a reason.

## 2. Problem and context
The repo has a client picker (`GET /v1/firm/clients/search`, SPEC-025) and the client record
columns (F-03-T25), but no clients index, record or reveal. P-07 builds CLI-01 and CLI-02 in
fixture mode ahead of the backend, so the contract comes first (AGENTS 15).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Every firm role | Reads clients (metadata only), after walls |
| Firm admin, partner (manager when live) | Edits the descriptor, office, relationship partner and status |
| Engagement partner, manager, EQR reviewer | Reveal a TIN with a reason (onshore, recent MFA) |
| Agent, system | Denied every clients action |

## 4. Goals and non-goals
**Goals:** the clients v1 routes, models and matrix rows (§8); flag `clients.v2`; the import ban
on the model gateway and agents for `organisations`.

**Non-goals:** contacts and portal access (CLI-04, `contacts-access.md`), intake and import
(CLI-06, `intake-import.md`), conflicts and screening (CLI-07/08), the TIN migration (P-07-T07).

## 5. User stories and acceptance criteria
### Story 1: the clients contract stub (P-07-T04)
- **AC-1** Every clients route in §8 exists with exactly one matrix action and documents 404 and 501.
- **AC-2** Client statuses are C2's generated enums (`ClientStatus`, `InvitationStatus` for the portal rollup); every field carries a classification tag; the list row carries no Restricted field and no TIN; a TIN appears only as `MaskedTinOut` (kind, presence, four digits, Restricted) on the record and in the one reveal response; no model has a hidden-by-wall field (DEC-43).
- **AC-3** `client.read` allows every firm role (a partner through their engagement roles until the derived `firm_partner` cell lands with the live index) and denies agent, system and client roles; `client.update` allows the firm admin and partners and denies agent and system; `tin.reveal` allows the engagement partner, manager and EQR reviewer only, requires `mfa_recent` and a reason, and denies agent, system and client roles.
- **AC-4** With `clients.v2` off every clients route answers 404; with it on, a stubbed route answers 501 `not_implemented`.
- **AC-5** No `organisations` module imports `abacus.ai_gateway` or `abacus.modules.agents` (import-linter contract and a source scan).

### Story 2: clients live (P-07-T08, T09, T10; epic Stories 1.1 to 1.3)
- **AC-6** CLI-01 a to f resolve from the E0 seed: `total` 184 at E0 (DEC-47), "Load more" by keyset; Lena Park's response has the same shape as for a firm without Ashford and `total` 183 (INV-3).
- **AC-7** A walled or unknown client answers 404 on every clients route; relationship edges into walled clients are omitted.
- **AC-8** PATCH with a stale `seen_version` answers 409 `stale_version`; prospect to active by a person answers 409 `illegal_transition`; each change writes one `client.updated` audit event.
- **AC-9** `tin.reveal` gains `not_offshore` with the live route; a reveal returns the value once with `Cache-Control: no-store` and one `tin.revealed` audit event with the reason code and never the value; an offshore member gets 403; no log line carries the value.

## 6. Behaviour and flows
| From | Event | To | Who can trigger |
|---|---|---|---|
| client `active` | a person marks it inactive or former | `inactive` / `former` | `client.update` |
| client `inactive` / `former` | a person reactivates | `active` | `client.update` |
| client `prospect` | first engagement accepted | `active` | system (DEC-62) |

## 7. Domain and data changes
No migration in the stub. P-07-T07 (M1) adds the sealed TIN columns, `tin_last4`, `tin_kind`,
`tin_status`, `tin_fingerprint`, `clients.descriptor` and `entity_relationships`.

## 8. Interfaces
Routes, models and actions: `docs/contracts/clients.md` §2 and §3 (code:
`backend/src/abacus/modules/organisations/contract.py`).

## 9. Authorisation and tenancy
- **Tenant scoping:** `tenant_session(ctx)` on every read and write.
- **Who can do what:** `docs/architecture/permission-matrix/organisations.yaml`. Conditions only narrow (DEC-132), so the manager path on `client.update`, the `firm_partner` cell on `client.read` and the preparer path on `tin.reveal` are added the DEC-132 way, and `not_offshore` on `tin.reveal` with its member facts, when the routes go live (DEC-141).
- **Ethical walls:** `visible(scope=client)`; walled clients are absent from rows, counts, facets and totals, and answer 404 (INV-3, DEC-43).
- **Client-side access:** none; client roles hold no clients action.

## 10. AI behaviour
N/A: no model call. `organisations` may not import the gateway or agents (AC-5).

## 11. Integrations
None.

## 12. Edge cases and failure modes
- A cursor from another filter set or firm: 422 `cursor_invalid` (F-03-T29).
- `q` matching nothing: an empty page with `total` 0, never an error.

## 13. Security and privacy
- **Data classification:** names confidential; identifiers and codes internal; masked TIN digits and the revealed value Restricted; no Restricted field in a list payload.
- **Threats considered:** wall disclosure through counts (none exist); TIN exposure (masked, reveal logged and human-only); `q` is never logged.

## 14. Audit trail and evidence integrity
`client.updated` and `tin.revealed` (reason code only), the human actor (INV-5). Reads are not audited, except reveals.

## 15. Observability
Reveal-volume metric (P-07-T10). Never log TINs or `q`.

## 16. Performance and scale
184 clients at E0; keyset pages of 50 (max 200); `total` exact up to 10,000.

## 17. UX
CLI-01 and CLI-02 screen contracts (`docs/screens/`); flag off shows F-05's flag-off ViewState.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-5 | unit (contract) | `backend/tests/contracts/clients/test_clients_stub.py` |
| AC-6 to AC-9 | integration | P-07-T13 (independent suite) |

## 19. Rollout
- **Feature flag:** `clients.v2` (default off, created 2026-10-23, expires 2027-04-21 under DEC-137: no flag may lapse before Feb 1, 2027).
- **Rollback:** the stub only adds routes behind the flag and matrix rows; revert the commit.

## 20. Open questions
- [ ] The derived firm-level manager grant for `client.update` and the preparer grant for `tin.reveal` (DEC-141). Settled by P-07-T09 and P-07-T10.

## 21. Future / explicitly deferred
CLI-03 relationship graph (T-06), the Tax profile tab (T-01), Files (N-01), Messages (N-03).
