# C3 · Review grammar (v1)

| Field | Value |
|---|---|
| Register row | C3 in `docs/contracts/README.md` |
| Version | v1 |
| Status | stub. Part 1 (sign-offs, review notes, human gates) is P-04-T07. Part 2 (decision cards, proposals, suggestions) is P-04-T08. Part 3 (issues, checkpoints, field provenance) is P-04-T11 |
| Provider epic | P-04 (`review` module; `agents` for suggestions and proposals, ADR-161) |
| Consumers | SHL-09, SHL-10, SHL-11, SHL-12, SHL-15, SHL-16 (P-04 UI); AUD-17 (A-06); HOME-01/02 (I-01); A-04, A-05, A-07, T-01, T-02, T-04, C-01, C-02, K-03, K-04 |
| Freeze sprint | Schema S3: recorded frozen by Fri Dec 11, 2026 (P-04-T09). Services S12: Fri Apr 16, 2027 (P-04-T27) |
| Flag | `review.grammar_api` (default off, expires 2027-01-20) |
| Spec | `docs/plan/epics/P-04.md` §3 (F1 to F5, F9), §4.3, §4.5 |
| ADRs | ADR-160 (review grammar, P-07), ADR-161 (suggestions, proposals, approval grants, Undo, P-35), P-36 (API conventions), ADR-031 (classification), ADR-089 (flags), ADR-005 (agents propose) |

## 1. Purpose
Every service line records a human judgement on prepared work the same way. A sign-off is a level on a ladder, bound to the content hash the signer saw. A review note blocks sign-off until a person clears it. The Home counts come from one projection. A judgement reserved to a role is a decision card whose options code computed. What the agent proposes is a proposal or a suggestion, which a named person approves, rejects or adopts. Consumers build SHL-10, SHL-11, SHL-12, AUD-17 and HOME-02 against these shapes in fixture mode while the services land. No route here lets an agent, system or support principal sign, clear, decide, approve or adopt (INV-1).

## 2. Who may call it
Part 1 (P-04-T07). Every route is behind `review.grammar_api`. Off, it answers 404. On, it answers 501 `not_implemented` until its service lands: sign-offs in P-04-T18, notes in P-04-T21, the projection in P-04-T16.

| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Sign-off ladder | `GET /v1/sign-offs?target_type=&target_id=` | `sign_off.read` | engagement partner, manager, senior, staff, reviewer, EQR reviewer (independence required) | denied |
| Eligibility for one level | `GET /v1/sign-offs/eligibility?target_type=&target_id=&level=` | `sign_off.read` | as above | denied |
| Record a sign-off | `POST /v1/sign-offs` | `sign_off.create`, then the level row in the service: L1 `sign_off.prepare`, L2 `sign_off.review`, L3 `sign_off.manager`, L4 `sign_off.partner`, L5 `sign_off.eqr` | the level row's roles | denied at every layer |
| Bulk sign-off | `POST /v1/sign-offs:bulk` with `Idempotency-Key` | `sign_off.bulk` | senior, manager, engagement partner | denied |
| Review notes, list | `GET /v1/review-notes?target_type=&target_id=&engagement_id=&status=&cursor=&limit=` | `review_note.read` | engagement partner, manager, senior, staff, reviewer, EQR reviewer | denied |
| Review note, detail | `GET /v1/review-notes/{note_id}` | `review_note.read` | as above; reading the sealed body is an access event (Q-02) | denied |
| Raise | `POST /v1/review-notes` | `review_note.raise` | engagement partner, manager, senior, reviewer | denied |
| Respond | `POST /v1/review-notes/{note_id}/respond` | `review_note.respond` | engagement partner, manager, senior, staff, reviewer | denied |
| Clear | `POST /v1/review-notes/{note_id}/clear` | `review_note.clear` | engagement partner, manager, senior, reviewer; only the raiser (service) | denied (and the event's CHECK) |
| Withdraw | `POST /v1/review-notes/{note_id}/withdraw` | `review_note.withdraw` | engagement partner, manager, senior, reviewer; only the raiser (service) | denied |
| What waits on me | `GET /v1/human-gates?assignee=me&kind=&engagement_id=&cursor=&limit=` | `human_gate.read` | firm admin, practice leader (in scope), quality partner, engagement partner, manager, senior, staff, reviewer, EQR reviewer | denied |

**Level actions (DEC-135).** The plan names the level actions `sign_off.l1` to `sign_off.l5`. The matrix already holds them as `sign_off.prepare`, `sign_off.review`, `sign_off.manager`, `sign_off.partner` and `sign_off.eqr` (SPEC-308), and live workpaper, trial-balance and mapping routes declare them. C3 keeps those names, so each level has one row and there are no aliases. Wherever the plan writes `sign_off.l<n>`, read the matching row above.

**Conditions arriving later.** P-04-T15 adds the matrix conditions `not_preparer_of_target` (L2, L3) and `reserved_role`, plus the generated I-AGENT-NEVER tests for every resolution action. Until then the service enforces segregation (R-SO-3).

The SPEC-313 routes under `/v1/engagements/{engagement_id}/review-notes` stay live. They are retired when the notes UI (A-06) reads `/v1/review-notes`.

Part 2 (P-04-T08) has the same flag and the same 404 and 501 behaviour. The services land in P-04-T23 (decision cards), P-04-T24 (proposals and suggestions) and P-04-T29 (Undo). Decision cards are `review`'s. Proposals and suggestions are `agents`' (ADR-161), and their matrix rows are in `agents.yaml`.

| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Decision cards, list | `GET /v1/decision-cards?engagement_id=&state=&cursor=&limit=` | `decision.read` | engagement partner, manager, senior, staff, reviewer, EQR reviewer (independence required) | denied |
| Decision card | `GET /v1/decision-cards/{card_id}` | `decision.read` | as above | denied |
| Decide | `POST /v1/decision-cards/{card_id}/decide` | `decision.decide` | engagement partner, manager, EQR reviewer; only the card's reserved role (service now, `reserved_role` condition in P-04-T15); MFA per kind | denied at every layer |
| Request more analysis | `POST /v1/decision-cards/{card_id}/analysis-requests` | `decision.request_analysis` | engagement partner, manager, senior, staff, reviewer, EQR reviewer | denied |
| Notify the reserved person | `POST /v1/decision-cards/{card_id}/notify` | `decision.notify` | engagement partner, manager, senior, staff | denied |
| Reassess | `POST /v1/decision-cards/{card_id}/reassess` | `decision.reassess` | engagement partner, manager | denied |
| Proposal | `GET /v1/proposals/{ref}`; `ref` is a UUID or `screening_result:`, `upload_review:` or `inbox_match:` plus an id | `proposal.read` | engagement partner, manager, senior, staff, reviewer, EQR reviewer | denied |
| Approve, or approve with edits | `POST /v1/proposals/{proposal_id}/approve` | `proposal.approve` | engagement partner, manager, senior; staff by `firm_setting(staff_can_accept_evidence)` (DEC-37) | denied at every layer |
| Reject | `POST /v1/proposals/{proposal_id}/reject` | `proposal.reject` | as approve | denied |
| Route to an approver | `POST /v1/proposals/{proposal_id}/route` | `proposal.route` | engagement partner, manager, senior | denied |
| Ask follow-up | `POST /v1/proposals/{proposal_id}/follow-up` | `proposal.follow_up` | engagement partner, manager, senior, staff | denied |
| Undo | `POST /v1/proposals/{proposal_id}/undo` | `proposal.undo` | as approve; only the decider, inside 10 s (service) | denied |
| Adopt or dismiss a suggestion | `POST /v1/suggestions/{suggestion_id}/adopt`, `.../dismiss` | `suggestion.resolve` (existing; conditions extended: `system: deny`, `independence: required`) | engagement partner, manager, senior | denied |
| Create a proposal (no route) | `agents.api.create_proposal` | `proposal.create` | none | agent: `task_scope` |

Raising a card is service-only, through `review.api.raise_decision_card` (P-04-T23), and has no route.

## 3. Models
Code: `backend/src/abacus/modules/review/contract.py`.

**Sign-offs**

- **`SignOffTargetOut`**. Confidential: `label` ("Trial Balance") and `context_label` ("Northwind Robotics 401(k) Plan · PY2025"). Internal: `target_type`, `target_id`, `version_no`, `content_hash`, `cell_count`, `citation_count`.
- **`SignOffOut`**, one insert-only row. All fields are internal:
  - `id`, `target_type`, `target_id`, `kind` (`ladder`, `field_tick` or `final_approval`);
  - `level` (`L1_preparer`, `L2_reviewer`, `L3_manager`, `L4_partner` or `L5_eqr`);
  - `signer_user_id`, `signer_name`, `initials`, `signed_at`;
  - `content_hash`, `version_no`, `statement_version`;
  - `adopted_run_id` and `adopted_run_number`, set on an L1 that adopts agent work (R-SO-8);
  - `stale`, which is computed: the row's hash differs from the target's current hash. No sign-off row is ever updated.
- **`LadderLevelOut`** (internal): `level`, `required`, `expected_signer_user_id`, `expected_signer_name`, and `latest`, which is a `SignOffOut` or null.
- **`SignOffLadderOut`**: `target`, `levels[]` and `allowed_actions[]`.
- **`SignOffEligibilityOut`**: `target`, `level`, `levels_allowed[]`, `ladder[]`, `checks[]`, `eligible` and `statement {version, text}`.
  - **`EligibilityCheckOut`**: `code`, `result` (`pass`, `fail` or `warn`), `facts` and `refs[]`.
  - The check codes are `open_review_notes`, `independence`, `segregation`, `all_cited`, `gate_g4`, `open_issues` and `eqr_limits`.
  - `facts` is Confidential. It holds the counts, names and dates the row's sentence needs. `refs` holds identifiers only: the open notes, the issues.
- **`SignOffIn`** (internal): `target_type`, `target_id`, `level`, `kind` (default `ladder`), `seen_hash` and `statement_version`. `seen_hash` is `sha256:` followed by the 64-hex digest (ADR-160 clause 3).
- **`BulkSignOffIn`**: `targets[] {target_type, target_id, seen_hash}` (1 to 50 targets), `level` and `statement_version`.
- **`BulkSignOffOut`**: `results[] {target_type, target_id, ok, sign_off_id, detail}`, `signed` and `excluded`. `detail` is one of the exclusion codes in §6.

**Review notes**

- **`ReviewNoteItemOut`**, a list row. Internal: `id`, `engagement_id`, `target_type`, `target_id`, `status`, `raised_by_user_id`, `raised_by_initials`, `raised_at`, `assignee_user_id`, `allowed_actions`. Confidential: `anchor {kind, ref}`, where `kind` is `cell`, `field`, `section` or `region` and `ref` is, for example, `RA!C14`.
- Bodies are sealed and Restricted. **List rows never carry a body.** `ReviewNoteOut` (the detail, and the response of every write) carries `note`, `body` (Restricted) and `events[] {event, body (Restricted), actor_user_id, actor_name, at}`. `event` is one of `raised`, `responded`, `cleared`, `closed`, `withdrawn` or `reopened`.
- **`RaiseReviewNoteIn`**: `target_type`, `target_id`, `anchor?` (Confidential), `body` (Restricted, 1 to 2,000 characters, no control characters) and `assignee_user_id?`.
- **`ReviewNoteEventIn`**: `body?` (Restricted).
- The list is the P-36 envelope. `counts` are per status.

**Human gates (C13 read)**

- **`HumanGateOut`** (internal): `id`, `kind`, `subject {type, id}`, `engagement_id`, `work_item_id`, `client_id`, `assignee_user_id`, `role`, `due_on`, `state` (`open`, `done` or `voided`) and `created_at`.
- `kind` is one of `decision`, `sign_off_request`, `proposal`, `send`, `final_approval`, `export` or `release` (DF-25).
- Labels come from the subject's owner at read time; the projection stores none.
- The list is the P-36 envelope. `counts` are per kind, so Home's "Waiting on you: 3 decisions, 6 sign-offs, 2 exports" is the same 11 on every surface.

**Decision cards (part 2)**

Code: `backend/src/abacus/modules/review/contract.py`.

- **`DecisionCardItemOut`**, a list row (internal): `id`, `engagement_id`, `work_item_id`, `kind`, `version_no`, `status`, `reserved_role`, `reserved_user_id`, `reserved_user_name`, `requested_at`, `blocking_count`, `superseded_by_version` and `allowed_actions`.
  - `reserved_role` is `engagement_partner`, `manager`, `eqr_reviewer` or `signer`.
  - No question, option or rationale is in a list row.
- **`DecisionCardOut`**, the detail:
  - `card`;
  - `question`, `context[] {key, label, value, citation_id}`, `options[]`, `factors[] {key, label, applicable, checked}` and `note` (Confidential);
  - `citation_ids` and `blocking_refs[]`;
  - `recommendation` (Confidential);
  - `decision` (Restricted);
  - `history[]`.
- **`DecisionOptionOut`**: `key`, `label`, `detail`, `figures` and `recommended`.
  - The kind's provider computes every option in code, never a model (ADR-050).
  - `figures` are decimal strings, for example `{"rate": "0.015", "materiality": "252200", ...}`.
- **`DecisionRecommendationOut`**: `suggestion_id`, `option_key` and `reasons[]`.
  - It is the agent's recommendation, a suggestion (`recommendation_suggestion_id`).
  - The UI shows it only as the tag "Recommended by Accrued Agent", and `reasons` render only through AgentText.
- **`DecisionOut`**: `id`, `option_key`, `factors[]`, `rationale` (Restricted, sealed), `seen_card_version`, `decided_by_user_id`, `decided_by_name` and `decided_at`.
- **`DecisionCardVersionOut`**: `version_no`, `event`, `actor_kind`, `actor_user_id`, `actor_initials`, `at`, `option_key`, `changed` and `figures`.
  - `event` is `proposed`, `decided` or `reassessed`.
  - `changed` is false for a reassessment with no change.
- **`DecideIn`**: `option_key`, `factors[]`, `rationale` (Restricted) and `seen_version`.
  - `rationale` is optional on the wire, so the service answers the fixed `422 rationale_required` rather than a schema error.
- **`AnalysisRequestIn`**: `text` (Restricted). It returns `AnalysisRequestOut {id, card_id, requested_by_user_id, requested_at}`.
- `notify` returns **`DecisionNotifyOut`**: `{card_id, notified_user_id, notified_at}`.
- `decide` and `reassess` return `DecisionCardOut`.

**Proposals and suggestions (part 2)**

Code: `backend/src/abacus/modules/agents/contract.py`.

Values may be return information (§7216) or client figures, so they are Restricted. They appear only in a detail read, never in a list.

- **`ProposalOut`**:
  - Internal: `ref`, `kind`, `state`, `version`, `agent_run_id`, `proposed_at`, `change_count`, `checkpoint_id`, `allowed_actions`.
  - Confidential: `title`, `context_label`, `evidence[] {evidence_version_id, label, citation_count}`, `set`.
  - Restricted: `reasoning` (agent text, rendered only through AgentText), `rows[]`, `totals[]`, `policy`, `decision`.
- **`ProposalRowOut`**: `n`, `suggestion_id`, `field_key`, `label`, `before` (Restricted), `after` (Restricted), `cause`, `citation_ids` and `unsupported`.
  - Values are strings, and numbers are decimal strings.
  - An `unsupported` row has no verified citation and blocks approval.
- **`ProposalTotalOut`**: `label`, `value` (Restricted) and `ties`. Code computes the totals row ("Net change to Form 1040 total income").
- **`ProposalPolicyOut`**: `policy_name`, `result` (`within_threshold` or `review_required`), `routed_to_user_id`, `routed_to_name` and `note` (agent text, Restricted).
  - While P-08 is dormant the approver is always a named person.
- **`ProposalSetOut`** (SHL-10 g): `set_type`, `set_id`, `label`, `results` and `exceptions`. The link row opens SHL-19 and approves nothing.
- **`ProposalDecisionOut`**, the latest `proposal_decisions` row: `id`, `decision`, `reason_code`, `note` (Restricted), `decided_by_user_id`, `decided_by_name`, `decided_at`, `routed_to_user_id` and `undo_until`.
  - `decision` is `approved`, `approved_with_edits`, `rejected`, `routed`, `follow_up` or `undone`.
  - `undo_until` is the end of the 10-second window (ADR-161 clause 6).
- **Requests:**
  - `ApproveProposalIn {seen_version, edits[] {n, after, citation_note}}`. Each edit needs a citation note, and the CTA reads "Approve with edits".
  - `RejectProposalIn {seen_version, reason_code, note?}`. `reason_code` is `wrong_treatment`, `unsupported_value`, `needs_client_input` or `other`.
  - `RouteProposalIn {seen_version, approver_user_id}`, `FollowUpIn {text}` and `UndoProposalIn {decision_id}`.
- **`SuggestionOut`**:
  - `id`, `target_type`, `target_id`, `field_key`;
  - `proposed_value` (Restricted) and `rationale` (agent text, Restricted);
  - `citation_ids`, `status`, `version`, `agent_run_id`;
  - `decision` (`adopted`, `edited`, `dismissed` or `undone`), `decided_by_user_id`, `decided_at`, `allowed_actions`.
- **`AdoptSuggestionIn`**: `seen_version`, `edited_value?` and `citation_note?`. An edit needs a note. **`DismissSuggestionIn`**: `seen_version` and `reason_code?`.

Agent text has no dedicated wire type yet: there is no `AgentTextValue` in the repo. These fields are plain strings, marked as agent text here and in their docstrings, and the web app renders them only through `AgentText` (frontend rule 2).

## 4. Status words
From `docs/product/status-vocabulary.yaml` (P-04-T02):

- `sign_off_slot`: `signed` ("✓ {initials}") and `stale` ("Changed after sign-off"). Both are derived and never stored.
- `review_note`: `open`, `responded`, `cleared`, `closed`, `withdrawn` (the generated `ReviewNoteStatus`).
- `decision_card`: `awaiting_role` ("Waiting on {person}"), `decided` ("Decided"; a reassessment with no change reads "No change" in history) and `superseded` ("Superseded by v{n}"). These are the generated `DecisionCardStatus`.
- `proposal`: `pending` ("Ready for review"), `approved` ("Approved by {person}"), `approved_with_edits`, `rejected` ("Rejected by {person} · reason: {reason}") and `superseded`. These are the generated `ProposalStatus`.
- `suggestion`: `pending`, `adopted` ("Adopted by {initials}"), `edited`, `dismissed`, `superseded` and `expired`. These are the generated `SuggestionStatus`.

## 5. Human-only actions
`sign_off.create`, `sign_off.bulk`, the five level rows, and `review_note.raise`, `.respond`, `.clear` and `.withdraw` all deny the agent. The sign-off rows and `review_note.withdraw` also deny `system` explicitly. Every other principal, support included, holds no cell, so it is denied.

The services add the other layers of ADR-160 clause 12:
- `require_live_human` comes first;
- `sign_offs.actor_kind = 'human'` is a CHECK bound to `app.actor_kind` (migration 0093);
- a `cleared` note event requires a human;
- the `SIGNOFF-001` static rule (P-04-T18).

Agent work is never shown as a sign-off. It is "Performed by Agent run #n under the direction of ‹person› · adopted by ‹initials›" on the L1 that adopted it.

Part 2 adds more resolution actions, each denying `agent` and `system` at the matrix:
- `decision.decide`;
- `proposal.approve`, `.reject`, `.route` and `.undo`;
- `suggestion.resolve`.

`decision.request_analysis`, `decision.notify`, `decision.reassess` and `proposal.follow_up` are a person's acts too, and deny both principals.

The agent holds only `proposal.create` and the existing `suggestion.create`, both through `task_scope`. Decision cards are raised through `review.api.raise_decision_card`.

The data layer adds the human-only CHECKs on `decisions`, `proposal_decisions` and `suggestion_decisions` (migrations 0094 and 0095), the 10-second Undo trigger, and the `DECISION-001` and `PROPOSAL-001` static rules (P-04-T23, T24). The agent is only ever "Recommended by Accrued Agent" or "proposed by Accrued Agent", never the decider or approver.

## 6. Errors
Every route on this page also answers:
- 404 `{"detail": "not found"}` when the flag is off, and for a walled or foreign target;
- 501 `{"detail": "not_implemented"}` when the flag is on and the service has not landed.

Fixed codes the services will answer:

| Status | Body | When |
|---|---|---|
| 409 | `{"detail": "content_changed"}` | the target's current hash differs from `seen_hash`; nothing is written |
| 409 | `{"detail": "open_review_notes", "facts": {"count": 2}}` | L2 and above while notes are open (R-SO-4) |
| 409 | `{"detail": "segregation"}` | the preparer at L2 or L3; the EQR at L1 to L4; the engagement partner as EQR (R-SO-3) |
| 409 | `{"detail": "independence_pending"}` | no current independence confirmation (R-SO-5, G2) |
| 409 | `{"detail": "incomplete"}` | an empty required field (R-SO-6) |
| 422 | `{"detail": "uncited_change", "facts": {"rows": [...]}}` | an uncited value (R-SO-6) |
| 403 | `{"detail": "level_not_permitted"}` | the level's row denies the caller (R-SO-2) |

Bulk items carry the same codes in `results[].detail`.

Part 2:

| Status | Body | When |
|---|---|---|
| 422 | `{"detail": "rationale_required"}` | decide without a rationale |
| 409 | `{"detail": "recommendation_changed"}` | decide or reassess on a stale card version |
| 403 | `{"detail": "mfa_required", "facts": {"max_age_s": 900}}` | the kind requires recent MFA (through `ConfirmItsYou`) |
| 403 | `{"detail": "forbidden"}` | a decide by anyone outside the card's reserved role |
| 409 | `{"detail": "proposal_changed"}` | approve, reject or route on a stale `seen_version` (existing evidence semantics) |
| 422 | `{"detail": "uncited_change", "facts": {"rows": [5]}}` | approve while a row has no verified citation |
| 403 | `{"detail": "forbidden", "facts": {"routed_to": "<user id>"}}` | approve above the viewer's threshold limit |
| 409 | `{"detail": "undo_window_closed"}` | Undo after 10 s or by another person |
| 409 | `{"detail": "effect_started"}` | Undo after the held effect started |

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `sign_off.recorded` (audit and outbox) | each sign-off, once per item in bulk | sign-off id, target type and id, level, content hash |
| `sign_off.resigned` (audit) | a new row at a level whose last row was stale | sign-off id, the stale row's id |
| `sign_off.went_stale` (outbox) | the target's hash moves past a signer's (P-04-T19) | sign-off id, target |
| `review_note.raised`, `.responded`, `.cleared`, `.withdrawn` (audit and outbox) | each note event | note id, target, event |
| `decision_card.raised`, `.superseded` (audit and outbox) | a card is raised or superseded | card id, kind, version |
| `decision.decided` (audit and outbox) | a decide; the owner applies it | card id, decision id, option key |
| `decision.reassessed`, `.analysis_requested`, `.notified` (audit) | reassess, request analysis, notify | card id, version |
| `proposal.approved`, `.approved_with_edits`, `.rejected`, `.routed`, `.undone`, `.follow_up_recorded` (audit); `proposal.decided`, `.undone` (outbox) | each proposal decision | proposal id, decision id, reason code |
| `suggestion.adopted`, `.edited`, `.dismissed`, `.undone` (audit); `suggestion.resolved` (outbox) | each suggestion decision | suggestion id, decision |

Reads of sealed note bodies and decision rationales are access events (Q-02 `access_events`). The notification kinds come from P-04-T26 (C16): `sign_off_requested`, `sign_off_stale`, `review_note_raised`, `decision_assigned` and `proposal_routed`.

## 8. Example payloads
Brightwater Hale E0: Northwind Robotics 401(k) Plan, PY2025, Mon Sep 14, 2026, 9:41 AM CT. Viewer Hannah Leclerc. Ids are placeholders, and the seed fixes them when P-04-T36 loads the scenario.

The content hash is written as SHL-12 shows it, `sha256:9f4c…e21a`. On the wire it is the full 64-hex digest, which the seed computes from Trial Balance v1's content (ADR-160 clause 3).

**SHL-12 a. Eligibility, Trial Balance v1 at L2.**
`GET /v1/sign-offs/eligibility?target_type=workpaper&target_id=<tb>&level=L2_reviewer`
```json
{"target": {"target_type": "workpaper", "target_id": "<tb>", "label": "Trial Balance",
            "context_label": "Northwind Robotics 401(k) Plan · PY2025", "version_no": 1,
            "content_hash": "sha256:9f4c…e21a", "cell_count": 14, "citation_count": 3},
 "level": "L2_reviewer",
 "levels_allowed": ["L1_preparer", "L2_reviewer", "L3_manager", "L4_partner"],
 "ladder": [
   {"level": "L1_preparer", "required": true, "expected_signer_user_id": null, "expected_signer_name": null,
    "latest": {"id": "<so-1>", "target_type": "workpaper", "target_id": "<tb>", "kind": "ladder",
               "level": "L1_preparer", "signer_user_id": "<marcus>", "signer_name": "Marcus Delaney",
               "initials": "MD", "signed_at": "2026-09-14T14:33:00Z", "content_hash": "sha256:9f4c…e21a",
               "version_no": 1, "statement_version": "<statement>", "adopted_run_id": "<run>",
               "adopted_run_number": 4127, "stale": false}},
   {"level": "L2_reviewer", "required": true, "expected_signer_user_id": null, "expected_signer_name": null, "latest": null},
   {"level": "L3_manager", "required": false, "expected_signer_user_id": null, "expected_signer_name": null, "latest": null},
   {"level": "L4_partner", "required": true, "expected_signer_user_id": "<margaret>", "expected_signer_name": "Margaret Okonkwo", "latest": null},
   {"level": "L5_eqr", "required": true, "expected_signer_user_id": "<thomas>", "expected_signer_name": "Thomas Whitcombe", "latest": null}],
 "checks": [
   {"code": "open_review_notes", "result": "pass", "facts": {"count": 0}, "refs": []},
   {"code": "independence", "result": "pass", "facts": {"person": "Hannah Leclerc", "confirmed_on": "2026-08-03"}, "refs": []},
   {"code": "segregation", "result": "pass", "facts": {"preparer": "Marcus Delaney"}, "refs": []},
   {"code": "all_cited", "result": "pass", "facts": {"cited": 14, "cells": 14}, "refs": []},
   {"code": "gate_g4", "result": "warn", "facts": {"awaiting": "Margaret Okonkwo"}, "refs": [{"type": "decision_card", "id": "<materiality-card>"}]}],
 "eligible": true,
 "statement": {"version": "<statement>", "text": "I reviewed this work. It is sufficient and appropriate, and its conclusions are supported."}}
```
SHL-12 renders the L1 detail as "Performed by Agent run #4127 under the direction of Marcus Delaney · adopted by MD".

**SHL-12 a′. Sign.**
`POST /v1/sign-offs`
```json
{"target_type": "workpaper", "target_id": "<tb>", "level": "L2_reviewer", "kind": "ladder",
 "seen_hash": "sha256:9f4c…e21a", "statement_version": "<statement>"}
```
The 201 response:
```json
{"id": "<so-2>", "target_type": "workpaper", "target_id": "<tb>", "kind": "ladder", "level": "L2_reviewer",
 "signer_user_id": "<hannah>", "signer_name": "Hannah Leclerc", "initials": "HL",
 "signed_at": "2026-09-14T14:41:00Z", "content_hash": "sha256:9f4c…e21a", "version_no": 1,
 "statement_version": "<statement>", "adopted_run_id": null, "adopted_run_number": null, "stale": false}
```
The screen then shows the toast "Signed off Trial Balance (L2) · 9:41 AM" and the header "✓ MD ✓ HL".

**SHL-12 b. Blocked by open notes (Risk Assessment v1).**
- The check row: `{"code": "open_review_notes", "result": "fail", "facts": {"count": 2}, "refs": [{"type": "review_note", "id": "<ra-c14>"}, {"type": "review_note", "id": "<ra-c22>"}]}`.
- A sign-off answers `409 {"detail": "open_review_notes", "facts": {"count": 2}}`.
- The two notes, from `GET /v1/review-notes?target_type=workpaper&target_id=<ra>&status=open`:
```json
{"items": [
  {"id": "<ra-c14>", "engagement_id": "<northwind>", "target_type": "workpaper", "target_id": "<ra>",
   "anchor": {"kind": "cell", "ref": "RA!C14"}, "status": "open", "raised_by_user_id": "<hannah>",
   "raised_by_initials": "HL", "raised_at": "<time>", "assignee_user_id": "<marcus>", "allowed_actions": ["review_note.clear"]},
  {"id": "<ra-c22>", "engagement_id": "<northwind>", "target_type": "workpaper", "target_id": "<ra>",
   "anchor": {"kind": "cell", "ref": "RA!C22"}, "status": "open", "raised_by_user_id": "<margaret>",
   "raised_by_initials": "MO", "raised_at": "<time>", "assignee_user_id": "<marcus>", "allowed_actions": []}],
 "next_cursor": null, "total": 2, "total_capped": false, "counts": {"open": 2}, "facets": {}}
```
- The detail of the first note (`GET /v1/review-notes/<ra-c14>`) has `"body": "Explain why participant loans are not a significant risk"`.

**SHL-12 c. Same preparer.** Marcus Delaney asks for L2 on Trial Balance. The check row is `{"code": "segregation", "result": "fail", ...}`, and a sign-off answers `409 {"detail": "segregation"}`. The dialog reads "You prepared this workpaper. A different reviewer must sign L2."

**SHL-12 e. Stale after change** (Thu Sep 24, 2:15 PM). Contributions receivable of $48,600 were added, so net assets are now $16,861,000 and Trial Balance's hash moved. Hannah's L2 row reads `"stale": true`, and SHL-12 offers only "Re-sign as Reviewer (L2)", which writes a new row.

**SHL-12 f. Bulk** (Thu Sep 24). The six rows are Trial Balance v1, Service Organizations & SOC 1 v1, Materiality v2, General Audit Planning v1, Internal Control v1, and Investments & Certification v1. Three are excluded with reasons, so the response has `"signed": 3, "excluded": 3`:
- Service Organizations & SOC 1 is `incomplete` ("Waiting on inputs");
- one is `open_review_notes` ("1 open note");
- one is `segregation` ("You prepared this").

**SHL-12 g. EQR viewer.** For Thomas Whitcombe, `levels_allowed` is `["L5_eqr"]`, and L1 to L4 answer `403 {"detail": "level_not_permitted"}`.

**Home.** `GET /v1/human-gates?assignee=me` returns `"counts": {"decision": 3, "sign_off_request": 6, "export": 2}`, which reads "Waiting on you: 3 decisions, 6 sign-offs, 2 exports".

### Part 2 examples
The clock and the ids follow part 1.

**SHL-11 a. Northwind planning materiality.** `GET /v1/decision-cards/<materiality-card>`, viewer Margaret Okonkwo, Mon Sep 14, 10:01 AM CT. The options foot as follows (F-04 §3.6 golden):
- 1.0% × 16,812,400 = 168,100;
- 1.5% = 252,200, with PM 75% = 189,150 and CT 5% = 12,610;
- the 1.0% option's PM is 126,075 and its CT is 8,405.
```json
{"card": {"id": "<materiality-card>", "engagement_id": "<northwind>", "work_item_id": "<audit>",
          "kind": "planning_materiality", "version_no": 1, "status": "awaiting_role",
          "reserved_role": "engagement_partner", "reserved_user_id": "<margaret>",
          "reserved_user_name": "Margaret Okonkwo", "requested_at": "2026-09-14T14:27:00Z",
          "blocking_count": 3, "superseded_by_version": null,
          "allowed_actions": ["decision.decide", "decision.request_analysis"]},
 "question": "Which planning materiality should the Northwind PY2025 audit use?",
 "context": [
   {"key": "benchmark", "label": "Benchmark", "value": "Net assets available for benefits, unadjusted, 12/31/2025", "citation_id": null},
   {"key": "amount", "label": "Amount", "value": "$16,812,400", "citation_id": "<harborline-p2>"},
   {"key": "firm_range", "label": "Firm range", "value": "0.5% – 2.0% of net assets (BH EBP v3 §4.2)", "citation_id": null},
   {"key": "prior_year", "label": "Prior year", "value": "PY2024: 1.5% of $14,228,500 = $213,400", "citation_id": null}],
 "options": [
   {"key": "pct_1_0", "label": "1.0% — $168,100",
    "detail": "Performance materiality 75% = $126,075 · clearly trivial 5% = $8,405. Lower end of the range; for elevated risk such as a new recordkeeper or prior misstatements.",
    "figures": {"rate": "0.010", "materiality": "168100", "performance_materiality": "126075", "clearly_trivial": "8405"},
    "recommended": false},
   {"key": "pct_1_5", "label": "1.5% — $252,200", "detail": "PM 75% = $189,150 · CT 5% = $12,610",
    "figures": {"rate": "0.015", "materiality": "252200", "performance_materiality": "189150", "clearly_trivial": "12610"},
    "recommended": true}],
 "factors": [
   {"key": "late_deposits", "label": "Late deposits of participant contributions are reported on Schedule H line 4a at any amount (specific materiality $0)", "applicable": true, "checked": true},
   {"key": "users", "label": "Users are participants, DOL and IRS through Form 5500; no lender or covenant use", "applicable": true, "checked": true},
   {"key": "first_year", "label": "First-year engagement or change in recordkeeper", "applicable": false, "checked": false}],
 "citation_ids": ["<bh-ebp-v3-4-2>", "<harborline-p2>", "<py2024-memo>"],
 "note": null,
 "recommendation": {"suggestion_id": "<suggestion>", "option_key": "pct_1_5",
   "reasons": ["Same basis and percentage as PY2024", "no misstatements above clearly trivial last year", "SOC 1 reports cover recordkeeping and custody"]},
 "blocking_refs": [{"type": "workpaper", "id": "<general-audit-planning>"}, {"type": "workpaper", "id": "<sample-selection>"}, {"type": "workpaper", "id": "<testing>"}],
 "decision": null,
 "history": [{"version_no": 1, "event": "proposed", "actor_kind": "agent", "actor_user_id": null, "actor_initials": null,
              "at": "2026-09-14T14:27:00Z", "option_key": "pct_1_5", "changed": null, "figures": {}}]}
```

**SHL-11 a to c. Decide.** `POST /v1/decision-cards/<materiality-card>/decide`
```json
{"option_key": "pct_1_5", "factors": ["late_deposits", "users"],
 "rationale": "Recurring engagement, stable plan, no prior misstatements above CT. 1.5% of net assets, consistent with PY2024.",
 "seen_version": 1}
```
The response has `card.status: "decided"`, `card.version_no: 2`, and the following decision:
```json
{"id": "<decision>", "option_key": "pct_1_5", "factors": ["late_deposits", "users"],
 "rationale": "Recurring engagement, stable plan, no prior misstatements above CT. 1.5% of net assets, consistent with PY2024.",
 "seen_card_version": 1, "decided_by_user_id": "<margaret>", "decided_by_name": "Margaret Okonkwo",
 "decided_at": "2026-09-14T15:02:00Z"}
```
The card reads "Margaret Okonkwo · Sep 14, 10:02 AM · v2: 1.5% = $252,200 · PM $189,150 · CT $12,610".

Errors:
- Without `rationale`, the decide answers `422 {"detail": "rationale_required"}`.
- With a `seen_version` older than the card's current version, it answers `409 {"detail": "recommendation_changed"}`.

**SHL-11 b. Awaiting role.** Hannah Leclerc reads the same card with `"allowed_actions": ["decision.notify", "decision.request_analysis"]` and no decide action. The banner reads "Waiting on Margaret Okonkwo · requested 9:27 AM". A decide by Hannah answers 403.

**SHL-11 d. Reassessed** (Tue Oct 6). History v3 is `{"version_no": 3, "event": "reassessed", "changed": false, "figures": {"benchmark": "16861000", "materiality": "252900", "difference": "700"}}`. That is 1.5% × 16,861,000 = 252,900, which is $700 from 252,200, so "no change".

**SHL-10 a. Feld K-1 treatment.** `GET /v1/proposals/<k1-proposal>`, viewer Samuel Ito, Mon Sep 14, 9:24 AM CT. The rows foot: 307,900 leaves line 28A (k) and enters line 28A (h), so the net change to Form 1040 total income is 0 (a tie). The QBI line is a separate form.
```json
{"ref": "<k1-proposal>", "kind": "field_change_set", "title": "K-1 treatment: Ridgeline",
 "context_label": "2025 Form 1040 · Feld", "state": "pending", "version": 1, "agent_run_id": "<run>",
 "proposed_at": "2026-09-14T14:18:00Z", "change_count": 4,
 "reasoning": "Prior-year treatment and the draft Ridgeline K-1 support passive classification. Jonah is a limited partner (box G) with no material participation, and the 2024 return reported Ridgeline as passive. The draft placed the income in nonpassive; this change restores passive treatment and records Ridgeline as qualified business income, preserving every other entry.",
 "rows": [
   {"n": 1, "suggestion_id": "<s1>", "field_key": "activity_classification.ridgeline", "label": "Activity classification · Ridgeline Property Partners, LP",
    "before": "Nonpassive", "after": "Passive", "cause": "K-1 box G; 2024 Sch E", "citation_ids": ["<c1>", "<c2>"], "unsupported": false},
   {"n": 2, "suggestion_id": "<s2>", "field_key": "sch_e.p2.28a_k", "label": "Sch E p. 2 line 28A (k) Nonpassive income from K-1",
    "before": "307900", "after": null, "cause": "moved to (h)", "citation_ids": ["<c1>"], "unsupported": false},
   {"n": 3, "suggestion_id": "<s3>", "field_key": "sch_e.p2.28a_h", "label": "Sch E p. 2 line 28A (h) Passive income from K-1",
    "before": null, "after": "307900", "cause": "K-1 box 2", "citation_ids": ["<c1>"], "unsupported": false},
   {"n": 4, "suggestion_id": "<s4>", "field_key": "f8995a.p1.l1.ridgeline", "label": "Form 8995-A Part I line 1 · Ridgeline QBI",
    "before": null, "after": "307900", "cause": "K-1 box 20 Z statement", "citation_ids": ["<c3>"], "unsupported": false}],
 "totals": [{"label": "Net change to Form 1040 total income", "value": "0", "ties": true}],
 "evidence": [
   {"evidence_version_id": "<k1-draft>", "label": "2025 Schedule K-1 — Ridgeline (Draft K-1 · pre-release)", "citation_count": 2},
   {"evidence_version_id": "<f1040-2024>", "label": "2024 Form 1040 — Schedule E, p. 2", "citation_count": 1},
   {"evidence_version_id": "<k1-stmt>", "label": "Ridgeline K-1 statement — box 20 code Z (§199A)", "citation_count": 1}],
 "policy": {"policy_name": null, "result": null, "routed_to_user_id": null, "routed_to_name": null,
            "note": "Return proposals need a Tax Reviewer. Final approval of this return stays with Daniel Reyes (BH-TAX-02). The K-1 is a draft — I'll re-verify these values when Ridgeline releases final K-1s (due Sep 15)."},
 "set": null, "checkpoint_id": null, "decision": null,
 "allowed_actions": ["proposal.approve", "proposal.reject", "proposal.follow_up"]}
```
- `POST /v1/proposals/<k1-proposal>/approve` with `{"seen_version": 1, "edits": []}` returns `state: "approved"` and `checkpoint_id: "<checkpoint-6>"` ("Approving creates Checkpoint 6").
- The decision is `{"decision": "approved", "decided_by_name": "Samuel Ito", ...}`, and `undo_until` is `decided_at` plus 10 s.
- TAX-07 logs "Proposal approved by Samuel Ito".

**SHL-10 c. Uncited value.** A fifth row:
```json
{"n": 5, "label": "Sch A line 5b Real estate taxes (co-op share)", "before": null, "after": "18240", "cause": null, "citation_ids": [], "unsupported": true}
```
Approve answers `422 {"detail": "uncited_change", "facts": {"rows": [5]}}` until the row is removed or cited.

**SHL-10 d. Over threshold** (Copperleaf, viewer Raj Malhotra). AJE-05 is 12,600.00 + 1,480.00 + 820.00 = 14,900.00. Its policy is:
```json
{"policy_name": "BH AJE thresholds v2", "result": "review_required", "routed_to_user_id": "<priya>", "routed_to_name": "Priya Raman"}
```
Approve by Raj answers 403 with `facts.routed_to`. `POST …/route` with `{"seen_version": 1, "approver_user_id": "<priya>"}` sends it, and the CTA reads "Send to Priya Raman for approval".

**SHL-10 f. Reject.** `POST /v1/proposals/<k1-proposal>/reject` with `{"seen_version": 1, "reason_code": "needs_client_input"}` reads "Rejected by Samuel Ito · reason: Needs client input".

**Suggestion adopt (SHL-10 b's single source change, as one suggestion).** `POST /v1/suggestions/<s-line-2a>/adopt` with `{"seen_version": 1}` adopts Form 1040 line 2a tax-exempt interest of 1,550 (K-1 box 18A). The response has `status: "adopted"` and `decision: "adopted"`.

## 9. Consumer contract tests
`backend/tests/contracts/review_grammar/` (P-04-T09) covers the SHL-10 a–g, SHL-11 a–h and SHL-12 a–h shapes against the stubs. The TypeScript fixture assertions run in the provider's stage 2. They fail if a field the artboards need is removed.

## 10. Versioning
Additive changes go in place. Breaking changes ship as v2 with one sprint of overlap.

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | (S3, Fri Dec 11, 2026) | | 2026-10-22: part 1 stub (P-04-T07): sign-offs, review notes and human gates. 2026-10-22: part 2 stub (P-04-T08): decision cards (`review`), proposals and suggestions (`agents`) |

## 11. Open points
- **Level actions.** The level actions keep their SPEC-308 names rather than `sign_off.l1` to `l5` (DEC-135).
- **Note bodies.** Note bodies are Restricted, so the list carries none. A detail route, `GET /v1/review-notes/{note_id}`, is added beyond the plan's table. Each body read is then one access event.
- **`sign_off.eqr` cell.** The row allows `reviewer` (SPEC-308). The F-03-T23 role `eqr_reviewer` is added to the reads and to `sign_off.create`. Moving `sign_off.eqr` to `eqr_reviewer` is P-04-T15's, with the generated deny tests.
- **Flag expiry.** `review.grammar_api` expires 2027-01-20, within the plan's Jan 1 to Apr 20 window, which it avoids for flags that live firms use. Live firms do not use this flag before the C3 services land. Its renewal moves the expiry past Apr 20.
- **Part 2 module split.** Decision cards are `review`'s (`review/contract.py`, `review.yaml`). Proposals and suggestions are `agents`' (`agents/contract.py`, `agents.yaml`), per ADR-160 clause 1 and ADR-161. One flag, `review.grammar_api`, covers both, and the agents routes read it from the kernel flag registry.
- **`proposal.create`.** It is added for the agent through `task_scope` (as `suggestion.create`), for `agents.api.create_proposal`. `decision_card.raise` arrives with its service function in P-04-T23.
- **Human-only audit register (Q-02-T17).** `decision.decided`, `proposal.approved` and `suggestion.adopted` join `docs/architecture/human-only-actions.yaml` with their services (P-04-T23, T24). That change needs its migration.
