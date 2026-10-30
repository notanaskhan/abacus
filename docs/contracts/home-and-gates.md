# C13 · Home and human gates (v1)

| Field | Value |
|---|---|
| Register row | C13 in `docs/contracts/README.md` |
| Version | v1 |
| Status | home half live (I-01-T10, 2026-10-27; client activity live, I-01-T12, DEC-900); gate half live (P-04-T16 list; the counts, I-01-T04; filters, presentation facts, snooze and reassign, I-01-T07, 2026-10-27) |
| Provider epic | I-01 (home half, AY) with P-04 (projection and gate half, N) |
| Consumers | HOME-01, HOME-02, SHL-04 (Approvals tab), I-02 (HOME-05, SHL-23), every gate-producing epic |
| Freeze sprint | S10 (starts 2027-03-08) |
| Flag | `home.dashboard` (default off, expires 2027-04-21, DEC-137); the gate half rides `review.grammar_api` |
| Spec | `docs/plan/epics/I-01.md` §4.3 and §8.2 |
| ADRs | ADR-160 (review grammar, clause 11), ADR-161; DF-25, DF-39, DEC-30, DEC-43 |

## 1. Purpose
Home shows one person what waits on them and how their practice stands. C13 has two halves. The **gate half** (P-04, `review`) is the `human_gates` projection, its registration slot, the queue and **the one count source** that every surface reads: the HOME-01 header and Approvals badge, the HOME-02 bands, the SHL-04 Approvals tab and I-02's brief. The **home half** (I-01, `practice` and `platform`) is `GET /v1/home`: tiles, the viewer's work, deadlines, client activity and the running count, with no queue in it, so no count is computed twice.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Home | `GET /v1/home?office_id=` | `home.read` (`practice.yaml`) | every firm role | denied; a client principal answers 404 (INV-4) |
| What waits on me | `GET /v1/human-gates?assignee=me&kind=&engagement_id=&state=&band=&office_id=&sort=&cursor=&limit=` | `human_gate.read` | as `review.yaml` | denied |
| The one count source | `GET /v1/human-gates/counts?office_id=` (I-01-T04, live behind `review.grammar_api`) | `human_gate.read` | as above | denied |
| Snooze, unsnooze | `POST /v1/human-gates/{id}/snooze` `{until}` · `/unsnooze` (I-01-T07) | `human_gate.snooze` | the gate's assignee | denied |
| Reassign | `GET /v1/human-gates/{id}/reassign-candidates` · `POST …/reassign` `{to_user_id, seen_version}` (I-01-T07) | `human_gate.reassign` | the reserved role's holder, or the EP or a manager on the engagement | denied |

Home is answered in this order: a client principal 404; `home.read` at the firm (403 for the agent, the system and anyone else refused); then the flag (off 404). Live since I-01-T10 (DEC-648).

## 3. Models
`backend/src/abacus/modules/practice/home_contract.py` (home half). Classification per field:

- **`HomeOut`** (`HomeVM`): `greeting` (Confidential), `tiles[]` (Internal), `your_work` (Confidential, null when the role has no assigned work band), `deadlines` (Confidential), `client_activity[]` (Confidential, the first 20; each row's codes and counts in `facts`, and since DEC-1001 an additive `labels` map of read-time names the sentence uses, `subject`, `recipient` and `context`, resolved now and never stored, empty until a source fills them), `running_count` (Internal, null when no owner registered `agent_runs_running`), `segments` (Internal).
- **`GreetingOut`**: `first_name` (Confidential), `date` (Internal; the firm's time zone on `kernel.clock`).
- **`HomeTileOut`**: `key` (the registered home count), `label` and `caption` (copy keys), `total`, `by_status[] {code, n, filter}`, `by_office[] {office_id, n}`, `target` (the route the tile opens). All Internal.
- **`YourWorkOut`**: `label` (copy key, Internal), `rows[] {work_item_id, name, client, status, function, tags}`; `name` and `client` Confidential.
- **`DeadlinesOut`**: `rows[] {work_item_id, due_on, client, filing_label, status, risk}` and `next`; `client` and `filing_label` Confidential; `risk` is a `due_risk` code computed by code.
- **`ClientActivityOut`**: `id`, `occurred_at`, `event_type` (allowlisted), `client_id`, `client_label` (Confidential, resolved at read time), `engagement_id`, `actor {type, id, label}` (label Confidential), `subject {type, id}`, `facts` (codes, ids, counts and booleans only; never free text or amounts).
- **`SegmentsOut`**: `deadlines`, `capacity`, `insights`, each `available`, `planned` (hidden in production) or `entitlement_missing` (DF-39; Insights behind the `insights` entitlement, DEC-55).

**The home-count slot** (`platform.register_home_count(key, provider)`; `platform/slots.py`): `provider(viewer, office_id) -> HomeCount(total, by_status, by_office, target_filter)`, counted by the owner under `visible()` and narrowed to the office. Fail closed: an unregistered key has no tile, and a provider that raises shows none rather than a wrong number. Keys planned: `audits`, `binders`, `closes`, `notices`, `portal_invites_pending`, `agent_runs_running` (queued excluded).

Gate-half models are `review`'s (`HumanGateOut`, `ListPage`): `docs/contracts/review-grammar.md` §3. I-01-T04 adds:

- **`HumanGateCountsOut`**: `total`, `bands {decisions, sign_offs, agent_outputs, approvals_sends}`, `overdue`, `snoozed`; all Internal. `total` is the sum of the bands and equals the list's `total` for the same caller. `overdue` counts the open, unsnoozed gates due before the firm's today; `snoozed` the open gates the caller snoozed until later (left out of `total`).
- **`HumanGateOut`** gains `subkind` (the owner's registered gate name, a code) and `office_id` (an identifier; a filter).

**I-01-T07 (DEC-646): the list and the acts.** The list takes `state` (`open`, the default, not snoozed by the caller; `snoozed`, open and snoozed by the caller until later; `done`), `band` (a DF-25 band), `office_id` (narrows, never authorises) and `sort` (`created`, oldest first; `deadline`, due first, undated last). Each `HumanGateOut` row gains the owner's presentation facts, resolved in one batch per owner (`review.api.register_gate_presenter`; the owner authorises each row and a row it leaves out has none; a presenter that fails leaves its rows bare): `bulk_eligible`, `subject_route`, `overlay`, `glyph`, `proposed_by` (`ProposedByOut {run_id, initiator_user_id, at}`, INV-5), and the existing `title` and `context`; and review's own `allowed_actions` (`human_gate.snooze`, `human_gate.reassign` when the owner registered a hook, each as the caller may on the gate's engagement) and `version` (one more than the gate's reassignments). Snooze takes `SnoozeIn {until}` and answers `SnoozedOut {gate_id, until}` (unsnooze: `until` is now). Reassign candidates answer `ReassignCandidatesOut {candidates [{user_id, role}]}`; reassign takes `ReassignIn {to_user_id, seen_version}` and answers `ReassignedOut {gate_id, to_user_id, version}`. A gate moves only through its owner's hook (`review.api.register_reassign_hook`): the decision card's (`review/card_reassign.py`) offers the card's reserved-role holders on the engagement, never the mover, never anyone walled off from the client, and lets the reserved person, the EP or a manager move it.

**Who a gate waits on (I-01-T04, DEC-570).** An open gate waits on its assignee; an unassigned gate waits on everyone who may read it (P-04), unless it names a `role`, when it waits on the people holding that role on the engagement (their team role) or in the firm (their firm role). A gate the caller snoozed until a later time leaves both the list and `total`. Walls and each source's own read action apply through `visible()` to the list and the counts alike, and nothing counts what was left out (DEC-43).

**Projection columns (0223).** `subkind` (set once, the source's registered name), `office_id` (the owner's, else the work item's, else the engagement's), `blocked`, `blocked_reason_code` (a code), `sort_hint`: kept in step with the owner by the projector like `state`. `python -m abacus_tools.reproject_human_gates <tenant-id>` re-projects one firm (idempotent; after an office change, which has no C13 event yet).

**I-01-T13 (DEC-803): `subject_route` codes.** A presenter's `subject_route` names a screen and its
ids, never a URL with data in it: `<SCREEN-ID>?<name>=<uuid>&…`. The SPA resolves it through its
manifest builders (`apps/web/src/screens/HOME-01/hosts.ts`) and opens nothing for a screen it does
not route or a value that is not a UUID. Codes in use:
- `AUD-03?auditId=<assurance work item>&item=<request item>`: an upload waiting on review on an
  assurance PBC list (assurance's `evidence_review` presenter);
- `BND-02?binderId=<request list>&request=<request item>`: an upload waiting on review on any other
  list (a tax binder, an intake list).
- `TAX-02?returnId=<tax return>`: a return's gate (DEC-1273); HOME-02 resolves it, no presenter
  emits it yet.
Gates without a presenter open by their own ids while `home.approvals` is off: acceptance on CLI-07;
independence conclusion, independence confirmation and EQR eligibility on CLI-08; agent outputs and
sends stay plain text until their host is built. SHL-04's Approvals tab counts with
`GET /v1/human-gates/counts` (its `total`), the same call as HOME-01's header and badge (P-01 R4).

## 4. Status words
From `docs/product/status-vocabulary.yaml`:
- `human_gate`: `open` ("Open"), `done` ("Done"), `voided` ("Voided"), and the derived per-viewer `snoozed` ("Snoozed until {date}").
- `due_risk` (derived, never stored): `overdue` ("Overdue"), `due_soon` ("{date} · {n} days", red-tint, 0 to 7 days), `approaching` ("{date} · {n} days", 8 to 14 days), `later` ("{date}").

**Band rule (DF-25).** `decision` → Decisions · `sign_off_request` → Sign-offs · `proposal` → Agent outputs · `send`, `final_approval`, `export`, `release` (and `evidence_review`, DEC-403, with I-01-T04) → Approvals & sends. Countersignatures are `send`. Band order is fixed; empty bands other than Decisions and Sign-offs are hidden. **Badge rule:** only the Approvals option of the Home segmented control carries a count, and it is the counts endpoint's `total`.

## 5. Human-only actions
Home writes nothing. Snooze and reassign (I-01-T07) deny the agent, the system and support at the matrix. At the database (I-01-T04, 0223): `human_gate_snoozes` and `human_gate_reassignments` are insert-only, `actor_kind = 'human'` is a CHECK on both, a trigger binds `actor_kind` and `actor_id` to the transaction's actor and a snooze's `user_id` to that same person. `decision_cards.reserved_user_id` is the app's one other writable card column; a trigger lets it move only for a person, on a card `awaiting_role`, with the status unchanged, never to the mover themself, by the reserved person, the engagement partner or a manager on the engagement, to a holder of the card's reserved role on the engagement who is not walled off from its client, in a transaction that wrote the matching reassignment row from the reserved person (DEC-575). A reassignment names its open gate's own subject; a snooze is of an open gate that waits on the snoozer and lasts at most 30 days (DEC-578). Deciding, signing and approving stay the owners' (C3).

## 6. Errors
Home: 404 `{"detail": "not found"}` for a client principal and with the flag off; 403 for a principal `home.read` refuses; the flag on answers Home (I-01-T10; 501 before it). The gate-half codes (I-01-T04, T07): 422 `snooze_past_due` (after the gate's due date in the firm's zone, or more than 30 days), `snooze_in_past`, `candidate_not_eligible` (not among the hook's candidates, or the owner's guard refused the move); 409 `gate_not_open`, `gate_overdue` (an overdue gate is never snoozed), `not_reassignable` (no hook; asked before the caller's permission), `stale_version` (`seen_version` behind). A gate the caller may not see is 404.

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| (none) | Home reads | Home reads write no audit or access event: nothing sealed is read |
| `human_gate.snoozed`, `.unsnoozed`, `.reassigned` (audit; I-01-T07) | a person snoozes, unsnoozes or reassigns | gate id, user ids, `until` |
| `human_gate.reassigned` (outbox; I-01-T07) | a reassignment | `gate_id`, `engagement_id`, `to_user_id`, `by_user`; its notification kind is `gate_reassigned` (the new person, never the mover) |

## 8. Example payloads
E0, Mon Sep 14, 2026 9:24 AM CT, Brightwater Hale (synthetic tenant), Daniel Reyes. Footing: Audits 17 + 15 + 11 + 7 = 50 of 79 work items; 27 audits; 11 of 22 closes; 9 notices with 2 New; Waiting on you 11 = 3 + 6 + 2.

`GET /v1/home` (live since I-01-T10):
```json
{"greeting": {"first_name": "Daniel", "date": "2026-09-14"},
 "tiles": [
   {"key": "audits", "label": "home.tile.audits", "caption": null, "total": 27,
    "by_status": [{"code": "planning", "n": 17, "filter": "phase=planning"}],
    "by_office": [], "target": "/audits"}],
 "your_work": null,
 "deadlines": {"rows": [], "next": null},
 "client_activity": [],
 "running_count": 0,
 "segments": {"deadlines": "planned", "capacity": "planned", "insights": "entitlement_missing"}}
```
The tile row above is the shape only; the full E0 tile set and rows are I-01-T05's fixtures, which foot to the figures above.

`GET /v1/human-gates/counts` (I-01-T04):
```json
{"total": 11, "bands": {"decisions": 3, "sign_offs": 6, "agent_outputs": 0, "approvals_sends": 2},
 "overdue": 0, "snoozed": 0}
```

## 9. Consumer contract tests
- Home half: `backend/tests/contracts/c13_home/test_home_stub.py` (the route, its action, flag-off 404, flag-on 501, client 404, agent and system 403, every field classified; the slot fails closed).
- Gate half (I-01-T03, ADR-078, written before I-01-T04 opens): `backend/tests/contracts/c13_home/test_c13_gate_half.py` and `backend/tests/ac/test_i01_c13_gate_half_ac.py`, strict xfails citing TASK-1304 until I-01-T04 and T07 land.

## 10. Versioning
Additive changes in place. Breaking changes ship as v2 with one sprint of overlap (see `docs/contracts/README.md`).

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | (S10 freeze, 2027-03-08) | — | home half stubbed 2026-10-26 (I-01-T02); counts, `subkind`, `office_id`, `evidence_review` added 2026-10-27 (I-01-T04); list filters, row facts, snooze, unsnooze, reassign added 2026-10-27 (I-01-T07) |

## 11. Open points
- P-07-T47 (DEC-539) registers `acceptance_decision_due`, `independence_conclusion_due`, `independence_confirmation_due` and `eqr_eligibility_due` through `register_gate_source` (`review/engagement_gates.py`); `subkind` (I-01-T04) carries that name. Each of these gates is assigned to a named person and shown only to them (`GateSource.assigned_only`, DEC-544).
- I-01-T08 (DEC-647) registers SPEC-004's review queue as `evidence_review` gates (subject `evidence_version`) and the home counts `agent_runs_running`, `audits` and `binders`; `portal_invites_pending` and the follow-up and invite-resend gates wait for their state.
- DEC-404 records the stub's choices (one `home.read` cell per firm role, the slot's fail-closed answer, the `due_risk` thresholds).
- OQ-2 is decided (DEC-403): an `evidence_review` class for SPEC-004 review assignments and uploads awaiting review, band Approvals & sends, added to the kind set additively with I-01-T04. The four bands are unchanged.
