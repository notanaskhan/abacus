# C3 · Review grammar (v1)

| Field | Value |
|---|---|
| Register row | C3 in `docs/contracts/README.md` |
| Version | v1 |
| Status | stub. Part 1 (sign-offs, review notes, human gates) is P-04-T07. Part 2 (decision cards, proposals, suggestions) is P-04-T08. Part 3 (issues and fix instructions, checkpoints, field provenance) is P-04-T11, an additive extension of the schema |
| Provider epic | P-04 (`review` module; `agents` for suggestions and proposals, ADR-161) |
| Consumers | SHL-09, SHL-10, SHL-11, SHL-12, SHL-15, SHL-16 (P-04 UI); AUD-17 (A-06); HOME-01/02 (I-01); A-04, A-05, A-07, T-01, T-02, T-04, C-01, C-02, K-03, K-04 |
| Freeze sprint | Schema S3: recorded frozen by Fri Dec 11, 2026 (P-04-T09). Services S12: Fri Apr 16, 2027 (P-04-T27) |
| Flag | `review.grammar_api` (default off, expires 2027-04-21 under DEC-137) |
| Spec | `docs/plan/epics/P-04.md` §3 (F1 to F9), §4.3, §4.5 |
| ADRs | ADR-160 (review grammar, P-07), ADR-161 (suggestions, proposals, approval grants, Undo, P-35), P-36 (API conventions), ADR-031 (classification), ADR-089 (flags), ADR-005 (agents propose) |

## 1. Purpose
Every service line records a human judgement on prepared work the same way. A sign-off is a level on a ladder, bound to the content hash the signer saw. A review note blocks sign-off until a person clears it. The Home counts come from one projection. A judgement reserved to a role is a decision card whose options code computed. What the agent proposes is a proposal or a suggestion, which a named person approves, rejects or adopts. Consumers build SHL-09, SHL-10, SHL-11, SHL-12, SHL-15, SHL-16, AUD-17 and HOME-02 against these shapes in fixture mode while the services land. An issue records what is wrong with a record, with an internal note and separate client wording. A checkpoint is a version of a target that a reviewer approves or restores, and a field's history shows who set each value, from what, citing what. No route here lets an agent, system or support principal sign, clear, decide, approve, adopt, resolve or tick (INV-1).

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

**Live (P-04-T18, T19; DEC-400 to DEC-402).** The ladder, eligibility and `POST /v1/sign-offs` are served by `review.sign_offs` behind the same flag (bulk with P-04-T22, below). A sign-off answers the fixed codes in §6 in this order: a non-person 403; `sign_off.create`; the level row (403 `level_not_permitted`, 409 `segregation` for a known preparer at L2 or L3, 409 `independence_pending`); the signer's own independence and, on an attest client, the G2 gate (409 `independence_pending`); `content_changed`; the statement version (422 `sign_off_invalid`); `incomplete`; `uncited_change`; `already_signed`; `open_review_notes`; `not_prepared` (L2 and above need a current L1); `segregation`. Statements are `reviewer-v1` (L1 to L4) and `eqr-v1` (L5). `allowed_actions` on the ladder names `sign_off.<level>` for each level the caller may sign now and `sign_off.resign.<level>` where that level's newest row is stale. `sign_off.eqr` grants `eqr_reviewer` beside `reviewer` (ADR-160 clause 4; DEC-401). The owners announce changes (`trial_balance.version_created`, `workpaper.content_changed`); the stale detector emits `sign_off.went_stale` once per sign-off and new hash, and `sign_off_stale` notifies the signer.

**Live (P-04-T21, T22; DEC-500, DEC-501, DEC-504).** The note routes are served by `review.notes` behind the same flag. Bodies are sealed (migration 0210) and a detail read records a `review_content.read` access event first; list rows carry no body and their `allowed_actions` name `review_note.respond`, `.clear` (the raiser or the engagement partner) and `.withdraw` (the raiser alone). A raise needs a registered reviewable (422 `unregistered_kind`, 404 for an unknown target); an assignee must be another person who may respond (422 `review_note_invalid`). Respond, clear and withdraw answer 409 `review_note_state` on a note that is not open or answered, and 409 `not_the_raiser`. Open and answered notes block L2 and above (R-SO-4); cleared and withdrawn notes do not. `review_note.raised` notifies the assignee, else the target's preparers (`review_note_raised`). Bulk sign-off signs each item through the single path; a stale second factor is 403 `mfa_required` `{max_age_s: 900}` (`sign_off.bulk` holds `mfa_recent`); an unknown, hidden or not-allowed item is excluded `level_not_permitted`; one target twice is 422 `sign_off_invalid`; the same key with another body is 422 `idempotency_key_reused`.

**Conditions arriving later.** P-04-T15 adds the matrix conditions `not_preparer_of_target` (L2, L3) and `reserved_role`, plus the generated I-AGENT-NEVER tests for every resolution action. Until then the service enforces segregation (R-SO-3).

The SPEC-313 routes under `/v1/engagements/{engagement_id}/review-notes` stay live. They are retired when the notes UI (A-06) reads `/v1/review-notes`.

**Live (P-04-T23; DEC-502, DEC-503).** The decision-card routes are served by `review.decisions`. A card is raised only through `review.api.raise_decision_card` (`decision_card.raise`, the agent through `task_scope`); its options are the kind's provider's, computed in code. `version_no` on a card is its newest history number (v1 proposed, then decided, then each reassessment), and `seen_version` must equal it. Decide answers, in order: 403 outside the reserved role and person; 403 `mfa_required` `{max_age_s}` when the kind asks for a recent factor (default 900 s); 409 `decision_card_state` once decided or superseded; 409 `recommendation_changed`; 422 `decision_invalid` for an unknown option or factor; 422 `rationale_required`. Reassess records No change as a new version with the provider's figures, or raises a superseding card whose first version is the reassessment. Notify is a `mention` to the named person (409 `decision_card_state` when nobody is named or the card is not awaiting); an analysis request is sealed. A rationale read is an access event.

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

Part 3 (P-04-T11) has the same flag and the same 404 and 501 behaviour. Every route is `review`'s, and its matrix rows are in `review.yaml`. The services land in P-04-T30 and T31 (issues), P-04-T32 (checkpoints) and P-04-T35 (field values).

| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Issues, list | `GET /v1/issues?record_type=&record_id=&engagement_id=&status=&kind=&cursor=&limit=` | `issue.read` | engagement partner, manager, senior, staff, reviewer, EQR reviewer | denied |
| Issue | `GET /v1/issues/{issue_id}` | `issue.read` | as above; reading the sealed texts is an access event (Q-02) | denied |
| Create | `POST /v1/issues` | `issue.create` | engagement partner, manager, senior, staff, reviewer | denied |
| Update and assign | `PATCH /v1/issues/{issue_id}` | `issue.update` | engagement partner, manager, senior, staff | denied |
| Resolve | `POST /v1/issues/{issue_id}/resolve` | `issue.resolve` | engagement partner, manager, senior, staff | denied at every layer (ISSUE-001) |
| Mark not applicable | `POST /v1/issues/{issue_id}/mark-not-applicable` | `issue.resolve` | as resolve | denied at every layer |
| Verify | `POST /v1/issues/{issue_id}/verify` | `issue.verify` | engagement partner, manager, senior; the reviewer functions on the work item (service now, `function_in` in P-04-T15) | denied at every layer |
| Reopen | `POST /v1/issues/{issue_id}/reopen` | `issue.reopen` | as verify | denied |
| Send to client | `POST /v1/issues/{issue_id}/send-to-client` with `Idempotency-Key` | `issue.send_to_client` | engagement partner, manager, senior, staff | denied |
| Fix instructions | `POST /v1/issues/{issue_id}/fix-instructions` | `fix_instruction.set` | engagement partner, manager, senior, staff | denied |
| Bulk fix instructions | `POST /v1/issues/fix-instructions:bulk` | `fix_instruction.set` | as above | denied |
| Explain | `POST /v1/issues/{issue_id}/explanations` | `issue.explain` | engagement partner, manager, senior, staff, reviewer | denied |
| Checkpoints of one target | `GET /v1/checkpoints?target_type=&target_id=&filter=agent\|named\|all` | `checkpoint.read` | engagement partner, manager, senior, staff, reviewer, EQR reviewer | denied |
| Checkpoint | `GET /v1/checkpoints/{checkpoint_id}?compare=previous\|current` | `checkpoint.read` | as above | denied |
| Save | `POST /v1/checkpoints` | `checkpoint.create` | engagement partner, manager, senior, staff | denied |
| Approve | `POST /v1/checkpoints/{checkpoint_id}/approve` | `checkpoint.approve` | engagement partner, manager, senior; the reviewer functions on the work item (service now, `function_in` in P-04-T15) | denied at every layer |
| Reject | `POST /v1/checkpoints/{checkpoint_id}/reject` | `checkpoint.reject` | as approve | denied at every layer |
| Restore as new | `POST /v1/checkpoints/{checkpoint_id}/restore` | `checkpoint.restore` | as approve | denied at every layer |
| Rename and star | `PATCH /v1/checkpoints/{checkpoint_id}` | `checkpoint.rename` | engagement partner, manager, senior, staff | denied |
| Field provenance | `GET /v1/fields/{target_type}/{target_id}/{field_key}/provenance` | `field.read` | engagement partner, manager, senior, staff, reviewer, EQR reviewer | denied |
| Edit a value | `PUT /v1/fields/{target_type}/{target_id}/{field_key}/value` | `field.edit` | engagement partner, manager, senior, staff; preparer functions (DEC-84; `function_in` in P-04-T15) | denied |
| Add a reference | `POST /v1/fields/{target_type}/{target_id}/{field_key}/references` | `field.add_reference` | engagement partner, manager, senior, staff | denied |
| Tick a field | `POST /v1/fields/{target_type}/{target_id}/{field_key}/ticks` | `field.sign_off` | engagement partner, manager, senior, staff, reviewer, as `sign_off.create`; the level row decides who may tick at which level | denied at every layer |
| Propose a checkpoint (no route) | `review.api.propose_checkpoint` | `checkpoint.propose` | none | agent: `task_scope`; the system cell for engine imports lands with P-04-T32 |

- **Beyond the plan's table.** `POST /v1/issues/{issue_id}/explanations` (`issue.explain`) serves SHL-15 d's "Explain…". Mark not applicable is a resolution, so it shares `issue.resolve`, as adopt and dismiss share `suggestion.resolve`.
- **One target's checkpoints.** `GET /v1/checkpoints` is one target's history, read like the sign-off ladder, so it answers `CheckpointHistoryOut` rather than the list envelope. Its summaries may carry return figures, so they are Restricted (§3).
- **Agent-raised issues.** Engine diagnostics and issues the agent raises come through `review.api.create_issue` (P-04-T30), with their own `task_scope` row then. The route's `issue.create` is a person's.
- **Conditions arriving later.** P-04-T15 adds `function_in(first_level_reviewer, detail_reviewer, manager_reviewer, signer)` to `checkpoint.approve`, `.reject` and `.restore`, the reviewer functions to `issue.verify`, and `function_in(preparer)` to `field.edit`. Conditions only narrow a row (DEC-132), so the role cells ship now and P-04-T15 narrows them. Until then the service checks (DEC-145). Tax Preparer and Tax Reviewer are work-item functions, not roles (DEC-21), so the repo's `reviewer` role (a read-only QC role) holds no part 3 write except raising an issue, asking for an explanation and a field tick, as it raises review notes and holds `sign_off.create` (P-04-T12).

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
- Bodies are sealed and Restricted. **List rows never carry a body.** `ReviewNoteDetailOut` (the detail, and the response of every write) carries `note`, `body` (Restricted) and `events[] {event, body (Restricted), actor_user_id, actor_name, at}`. `event` is one of `raised`, `responded`, `cleared`, `closed`, `withdrawn` or `reopened`.
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
- **`CardDecisionOut`**: `id`, `option_key`, `factors[]`, `rationale` (Restricted, sealed), `seen_card_version`, `decided_by_user_id`, `decided_by_name` and `decided_at`.
- **`DecisionCardVersionOut`**: `version_no`, `event`, `actor_kind`, `actor_user_id`, `actor_initials`, `at`, `option_key`, `changed` and `figures`.
  - `event` is `proposed`, `decided` or `reassessed`.
  - `changed` is false for a reassessment with no change.
- **`CardDecideIn`**: `option_key`, `factors[]`, `rationale` (Restricted) and `seen_version`.
  - `rationale` is optional on the wire, so the service answers the fixed `422 rationale_required` rather than a schema error.
- **`AnalysisRequestIn`**: `text` (Restricted). It returns `AnalysisRequestOut {id, card_id, requested_by_user_id, requested_at}`.
- `notify` returns **`DecisionNotifyOut`**: `{card_id, notified_user_id, notified_at}`.
- `decide` and `reassess` return `DecisionCardOut`.

**Proposals and suggestions (part 2)**

Code: `backend/src/abacus/modules/agents/contract.py`.

Values may be return information (§7216) or client figures, so they are Restricted. They appear only in a detail read, never in a list.

- **`AgentProposalOut`**:
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
- **`AgentSuggestionOut`**:
  - `id`, `target_type`, `target_id`, `field_key`;
  - `proposed_value` (Restricted) and `rationale` (agent text, Restricted);
  - `citation_ids`, `status`, `version`, `agent_run_id`;
  - `decision` (`adopted`, `edited`, `dismissed` or `undone`), `decided_by_user_id`, `decided_at`, `allowed_actions`.
- **`AdoptSuggestionIn`**: `seen_version`, `edited_value?` and `citation_note?`. An edit needs a note. **`DismissSuggestionIn`**: `seen_version` and `reason_code?`.

Agent text has no dedicated wire type yet: there is no `AgentTextValue` in the repo. These fields are plain strings, marked as agent text here and in their docstrings, and the web app renders them only through `AgentText` (frontend rule 2).

**Issues and fix instructions (part 3)**

Code: `backend/src/abacus/modules/review/contract.py`. Titles, notes, client wording, instructions and agent text may be return information or client figures, so they are Restricted and appear only in the detail.

- **`IssueItemOut`**, a list row (internal): `id`, `engagement_id`, `work_item_id`, `record {type, id}`, `kind`, `priority`, `status`, `instructions_required`, `assignee_user_id`, `assignee_name`, `assignee_agent`, `blocks[]`, `link_count`, `version`, `created_at`, `allowed_actions`.
  - `kind` is `missing_information`, `action_required`, `review_point`, `waiting_on_client`, `exception` or `engine_diagnostic`. The four §3.3.1 kind lines are labels on an issue, not states.
  - `priority` is the generated `IssueSeverityStatus` (`high`, `medium`, `low`), and `status` is the generated `IssueStatus`.
  - `blocks[]` holds `final_approval`, `export`, `release` or `sign_off`.
  - **No title is in a list row.** It is sealed and Restricted.
- **`IssueDetailOut`**, the detail and the response of every issue write:
  - `issue` and `record_label` (Confidential, "2025 Form 1040 · Jonah & Claire Feld");
  - `title`, `internal_note` and `client_wording` (Restricted, sealed);
  - `client_contact {contact_id, name, role_label}` (Confidential);
  - `links[] {kind, label, target_type, target_id, anchor}` (Confidential), where `kind` is `cell_range`, `form_field`, `file`, `request_item` or `finding`;
  - `suggestion {text, agent_run_id, suggested_at}`, agent text rendered only through AgentText (Restricted);
  - `fix_instructions {text, scope, set_by_user_id, set_by_name, set_at}` (Restricted). `scope` is `this_issue` or `all_of_class`;
  - `fix_run {agent_run_id, label, status, proposal_id}` (Restricted). `status` is the generated `AgentRunStatus`, and `label` is agent text;
  - `explanations[] {id, text, agent_run_id, explained_at, citations[] {citation_id, label}, pinned}` (Restricted);
  - `request_item_id`, set once the client wording was sent;
  - `events[] {event, actor_kind, actor_user_id, actor_name, at}`. `event` is one of the ten `issue_events` codes.
- **Requests:**
  - `IssueCreateIn {record_type, record_id, kind, priority, title, internal_note?, client_wording?, client_contact_id?, assignee_user_id?, assignee_agent, links[] {kind, target_type?, target_id?, anchor?}, blocks[]}`.
  - `IssueUpdateIn {seen_version, title?, kind?, priority?, assignee_user_id?, assignee_agent?}`.
  - `IssueResolutionIn {seen_version, note?}` for resolve, verify, reopen and mark not applicable.
  - `IssueSendToClientIn {seen_version, client_wording, contact_id, due_on?}`, with an `Idempotency-Key`.
  - `FixInstructionsIn {seen_version, text, scope}`. It answers 202 `FixInstructionsAcceptedOut {issue_id, agent_run_id, status}`.
  - `BulkFixInstructionsIn {issues[] {issue_id, seen_version}, text}` (1 to 50 issues). It answers 202 `BulkFixInstructionsOut {results[] {issue_id, ok, agent_run_id, detail}, accepted, excluded}`.
  - Explain takes no body and answers 202 `ExplainAcceptedOut {issue_id, agent_run_id}`.
- Fix runs always propose (DF-13), so the "Propose changes for my approval" box is not a wire field.

**Checkpoints (part 3)**

- **`CheckpointItemOut`**, one card:
  - Internal: `id`, `target_type`, `target_id`, `seq`, `starred`, `author_kind` (`agent`, `person` or `import`), `author_user_id`, `author_name`, `cause`, `status`, `current`, `created_at`, `content_hash`, `proposal_id`, `restored_from_id`, `agent_run_id`, `allowed_actions`.
  - Confidential: `name`. A card reads "Checkpoint {seq}" unless it is named.
  - Restricted: `summary` ("Corrected Halvard 1099-INT (2,190 → 2,310)") and `decision`.
  - `status` is the generated `CheckpointStatus`. `current` is computed and never stored.
- **`CheckpointDecisionOut`**: `id`, `decision` (`approved`, `rejected` or `restored`), `reason` (Restricted, sealed), `decided_by_user_id`, `decided_by_name`, `decided_at` and `proposal_decision_id`.
- **`CheckpointHistoryOut`**: `target_type`, `target_id`, `filter`, `items[]` (newest first), `current_checkpoint_id`, `total` and `allowed_actions`.
- **`CheckpointDetailOut`**: `checkpoint`, `compare` (`previous` or `current`), `compared_to_id`, `steps[]`, `diff[]` and `totals[]`.
  - `CheckpointStepOut {kind, title, detail, at}`. `kind` is `analyzed`, `updated_worksheet`, `created_worksheet`, `skipped_worksheet`, `self_check` or `imported`. `detail` is Restricted.
  - `CheckpointDiffRowOut {field_key, label, old, new, cause, citation_ids}`. Code computes `old` and `new` (Restricted). Values are strings, numbers are decimal strings, and null is an empty cell.
  - `CheckpointTotalOut {label, value, ties}`. Code computes it ("Net change to total income · 0").
- **Requests:** `CheckpointCreateIn {target_type, target_id, name?}`; `CheckpointApproveIn {seen_hash}`; `CheckpointRejectIn {seen_hash, reason}`; `CheckpointRestoreIn {seen_hash}`; `CheckpointRenameIn {name?, starred?}`. Approve, reject and rename answer `CheckpointItemOut`. Save and restore answer 201 with the new checkpoint.

**Field provenance (part 3)**

- **`FieldProvenanceOut`**, the tray and the response of every field write: `target_type`, `target_id`, `field_key`, `label` (Confidential), `current_seq`, `content_hash`, `versions[]` (newest first, Restricted), `ticks[]`, `flags[]` (Restricted) and `allowed_actions`.
- **`FieldVersionOut`**, one insert-only `field_value_versions` row:
  - `seq`; `value {t, v}` (Restricted), where `t` is `decimal`, `text`, `date` or `bool` and decimals are strings;
  - `value_kind` (`exact` or `estimate`), `value_source`, `cause`;
  - `actor_kind`, `actor_user_id`, `actor_name`, `recorded_at`;
  - `citation` (Restricted): the C4 citation sentence, or a person's required citation note on an edit;
  - `citation_ids`, and `references[] {id, kind, label, detail, citation_id, document_id, page}` (Restricted), where `kind` is `document`, `engine_import`, `workpaper` or `prior_return`;
  - `unsupported`, which is computed: no verified citation;
  - `suggestion_id`, `checkpoint_id` and `issue_id`. An estimate links its open issue.
  - `value_source` never carries `policy` while `fvv_policy_dormant` holds.
- **`FieldTickOut`**: `sign_off_id`, `level`, `signer_user_id`, `signer_name`, `initials`, `signed_at`, `content_hash` and `stale` (computed). A tick is a `field_tick` sign-off.
- **`FieldFlagOut`**: `note_id`, `raised_by_user_id`, `raised_by_initials`, `raised_at`, `body` (Restricted) and `status`. A flag is a review note anchored on the field.
- **Requests:** `FieldEditIn {value {t, v}, value_kind, citation_note, seen_seq}`, where the note is required; `FieldReferenceIn {document_id, page?, seen_seq}`; `FieldTickIn {level, seen_hash}`.

## 4. Status words
From `docs/product/status-vocabulary.yaml` (P-04-T02):

- `sign_off_slot`: `signed` ("✓ {initials}") and `stale` ("Changed after sign-off"). Both are derived and never stored.
- `review_note`: `open`, `responded`, `cleared`, `closed`, `withdrawn` (the generated `ReviewNoteStatus`).
- `decision_card`: `awaiting_role` ("Waiting on {person}"), `decided` ("Decided"; a reassessment with no change reads "No change" in history) and `superseded` ("Superseded by v{n}"). These are the generated `DecisionCardStatus`.
- `proposal`: `pending` ("Ready for review"), `approved` ("Approved by {person}"), `approved_with_edits`, `rejected` ("Rejected by {person} · reason: {reason}") and `superseded`. These are the generated `ProposalStatus`.
- `suggestion`: `pending`, `adopted` ("Adopted by {initials}"), `edited`, `dismissed`, `superseded` and `expired`. These are the generated `SuggestionStatus`.


Part 3:

- `issue`: `open` (sub-state "Instructions required"), `in_progress` ("In progress"; the agent fixing), `resolved`, `verified`, `reopened` and `not_applicable`. These are the generated `IssueStatus`. The `issue_audit_route` codes (`under_evaluation`, `converted_to_misstatement`, `converted_to_deficiency`) share the `issues.status` CHECK, but no SHL-15 frame shows them, so they reach the wire with AUD-15's contract (A-06), not here.
- `issue_severity`: `high`, `medium` and `low`, the issue's `priority` (the generated `IssueSeverityStatus`).
- `checkpoint`: `proposed`, `approved` ("Approved · {person} · {time}"), `rejected` ("{person} · reason: {reason}") and `saved` (the generated `CheckpointStatus`). `current` is derived: the wire has a computed `current` boolean and no stored status.
- `field_value`: `updated`, `edited`, `estimate` ("≈") and `unsupported` are all derived, never stored. The wire carries `value_source`, `value_kind`, the earlier versions and the computed `unsupported`.
- `agent_run`: `fix_run.status` is the generated `AgentRunStatus` ("Running" on SHL-15 a-prime).

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


Part 3 adds more actions that deny `agent` and `system` at the matrix:
- the resolutions `issue.resolve` (with mark not applicable), `issue.verify` and `issue.reopen`, and `checkpoint.approve`, `.reject` and `.restore`;
- `field.sign_off`, a `field_tick` sign-off.

`issue.create`, `.update`, `.send_to_client` and `.explain`, `fix_instruction.set`, `checkpoint.create` and `.rename`, and `field.edit` and `.add_reference` are a person's acts too, and deny both principals.

The agent holds only `checkpoint.propose`, through `task_scope`, with no route. The system principal gets it for engine imports with P-04-T32, when the contract set of system actions grows with its service. The agent never resolves its own issue (`ISSUE-001`, P-04-T31). A fix run's output is a proposal that a person approves in SHL-10, never a direct edit (DF-13). The data layer adds the human-only CHECK on `checkpoint_decisions` and the resolution CHECK on `issue_events` (migration 0094), and `field_value_versions` requires a citation note on every human edit (`fvv_human_edits_cite`, migration 0093). Only `send-to-client` creates anything a client can see, and it carries only the client wording (INV-4).

## 6. Errors
Every route on this page also answers:
- 404 `{"detail": "not found"}` when the flag is off, and for a walled or foreign target;
- 501 `{"detail": "not_implemented"}` when the flag is on and the service has not landed.

Fixed codes the services will answer:

| Status | Body | When |
|---|---|---|
| 409 | `{"detail": "content_changed"}` | the target's current hash differs from `seen_hash`; nothing is written |
| 409 | `{"detail": "open_review_notes", "facts": {"count": 2}}` | L2 and above while notes are open (R-SO-4) |
| 409 | `{"detail": "segregation"}` | the preparer (the owner's preparers and every L1 signer) at L2 or L3 (R-SO-3). The EQR at L1 to L4 and the engagement partner at L5 hold no level row, so they answer 403 `level_not_permitted` (P-04 F2, SHL-12g) |
| 409 | `{"detail": "independence_pending"}` | no current independence confirmation (R-SO-5, G2) |
| 409 | `{"detail": "incomplete", "facts": {"count": 2}}` | empty required fields (R-SO-6) |
| 422 | `{"detail": "uncited_change", "facts": {"count": 1}}` | uncited agent values (R-SO-6); facts are identifiers only, so a count (ADR-139) |
| 409 | `{"detail": "not_prepared"}` | L2 and above without a current L1 |
| 409 | `{"detail": "already_signed"}` | the caller signed this level on this exact content |
| 422 | `{"detail": "sign_off_invalid", "facts": {"field": "statement_version"}}` | a statement version that isn't the level's current one, or a kind not served yet |
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


Part 3:

| Status | Body | When |
|---|---|---|
| 409 | `{"detail": "issue_changed"}` | an issue write on a stale `seen_version` |
| 409 | `{"detail": "fix_runner_unavailable"}` | fix instructions or Explain while no runner is registered for the record's owner (the sheet's agents-off state) |
| 409 | `{"detail": "gate_unmet", "facts": {"gate": "G3"}}` | send to client before the G3 gate is met |
| 409 | `{"detail": "checkpoint_changed"}` | approve, reject or restore when the checkpoint is no longer as seen (`seen_hash`, or no longer `proposed`) |
| 403 | `{"detail": "forbidden"}` | approve, reject or restore by someone without a reviewer function on the work item |
| 409 | `{"detail": "field_changed"}` | an edit or a reference on a stale `seen_seq` |
| 409 | `{"detail": "content_changed"}` | a field tick on a value whose hash moved |
| 422 | `{"detail": "uncited_change"}` | a field tick on an unsupported value ("Add a reference before signing off") |

Bulk fix-instruction items carry `issue_changed`, `fix_runner_unavailable` or `level_not_permitted` in `results[].detail`. An edit without a citation note fails the schema (422).

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
| `issue.created`, `.assigned`, `.fix_instructions_set`, `.explained`, `.resolved`, `.verified`, `.reopened`, `.marked_not_applicable`, `.sent_to_client` (audit); `issue.created`, `.assigned`, `.status_changed`, `.sent_to_client` (outbox) | each issue event | issue id, record, event |
| `checkpoint.proposed`, `.created`, `.approved`, `.rejected`, `.restored`, `.renamed` (audit); `checkpoint.created`, `.approved`, `.rejected`, `.restored` (outbox) | each checkpoint event; `checkpoint.approved` carries the amount deltas (DEC-85) | checkpoint id, target, decision id, delta facts |
| `field.value_edited`, `.reference_added` (audit); `field.value_recorded` (outbox); a tick writes `sign_off.recorded` | each field write | target, field key, seq |

Reads of sealed note bodies, decision rationales and issue texts are access events (Q-02 `access_events`). The notification kinds come from P-04-T26 (C16): `sign_off_requested`, `sign_off_stale`, `review_note_raised`, `decision_assigned` and `proposal_routed`.

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

### Part 3 examples
Brightwater Hale E0: the Feld 2025 Form 1040 (Jonah & Claire Feld), Mon Sep 14, 2026, 9:24 AM CT, viewer Samuel Ito unless a frame names another. Ids are placeholders, as in parts 1 and 2. An instant the artboard shows only as a date is written at noon CT, and `"<time>"` is an instant no artboard shows; the seed fixes both (P-04-T36). Hashes are written abbreviated, as in part 1.

**SHL-09 a. Halvard interest, 2,190 → 2,310.** `GET /v1/fields/tax_return/<feld-1040>/sch_b.p1.l1.halvard/provenance`. The agent changed the value from the corrected 1099-INT when Kevin Osei approved Checkpoint 4. Kevin's earlier tick was on the imported value, so its hash no longer matches and it reads stale ("✓ KO · Sep 8 (before this change)", "Changed after sign-off").
```json
{"target_type": "tax_return", "target_id": "<feld-1040>", "field_key": "sch_b.p1.l1.halvard",
 "label": "Taxable interest — Halvard Securities", "current_seq": 2, "content_hash": "sha256:7d20…c4b1",
 "versions": [
   {"seq": 2, "value": {"t": "decimal", "v": "2310"}, "value_kind": "exact", "value_source": "agent_suggested",
    "cause": "suggestion_adopted", "actor_kind": "agent", "actor_user_id": null, "actor_name": "Accrued Agent",
    "recorded_at": "2026-09-10T19:12:00Z",
    "citation": "Box 1 of the corrected Halvard Securities 2025 Form 1099-INT (issued Mar 6, 2026), consolidated statement p. 4.",
    "citation_ids": ["<c-halvard-corrected>"],
    "references": [
      {"id": "<ref-import-v3>", "kind": "engine_import", "label": "Imported Return — CCH Axcess 2025I:FeldJ:V3 (prior value 2,190)",
       "detail": null, "citation_id": null, "document_id": null, "page": null},
      {"id": "<ref-halvard-corrected>", "kind": "document", "label": "Halvard Securities 2025 Consolidated 1099 (Corrected) · p. 4",
       "detail": "Interest income, Box 1: 2,310.00", "citation_id": "<c-halvard-corrected>", "document_id": "<doc-halvard-corrected>", "page": 4}],
    "unsupported": false, "suggestion_id": "<s-halvard>", "checkpoint_id": "<checkpoint-4>", "issue_id": null},
   {"seq": 1, "value": {"t": "decimal", "v": "2190"}, "value_kind": "exact", "value_source": "engine_import",
    "cause": "import", "actor_kind": "system", "actor_user_id": null, "actor_name": "Imported Return",
    "recorded_at": "2026-08-28T15:46:00Z",
    "citation": "Box 1 of the original Halvard Securities 2025 Form 1099-INT (issued Feb 14, 2026), p. 4.",
    "citation_ids": ["<c-halvard-original>"],
    "references": [
      {"id": "<ref-import-v3>", "kind": "engine_import", "label": "Imported Return — CCH Axcess 2025I:FeldJ:V3",
       "detail": null, "citation_id": null, "document_id": null, "page": null}],
    "unsupported": false, "suggestion_id": null, "checkpoint_id": "<checkpoint-2>", "issue_id": null}],
 "ticks": [
   {"sign_off_id": "<tick-ko>", "level": "L1_preparer", "signer_user_id": "<kevin>", "signer_name": "Kevin Osei",
    "initials": "KO", "signed_at": "2026-09-08T17:00:00Z", "content_hash": "sha256:e913…5a02", "stale": true}],
 "flags": [
   {"note_id": "<flag-si>", "raised_by_user_id": "<samuel>", "raised_by_initials": "SI", "raised_at": "2026-09-11T17:00:00Z",
    "body": "Confirm corrected 1099 replaces the original", "status": "open"}],
 "allowed_actions": ["field.edit", "field.add_reference", "field.sign_off"]}
```
The footer reads "2 versions". "Sign off field" posts `{"level": "L2_reviewer", "seen_hash": "sha256:7d20…c4b1"}` to `…/ticks`, with the full digest on the wire, and adds "✓ SI · now".

**SHL-09 b. Estimate.** The one version of "2025 federal estimated tax payments" is an estimate that links the open Feld issue. Four vouchers of 12,000 foot to 48,000.
```json
{"seq": 1, "value": {"t": "decimal", "v": "48000"}, "value_kind": "estimate", "value_source": "agent_suggested",
 "cause": "suggestion_adopted", "actor_kind": "agent", "actor_user_id": null, "actor_name": "Accrued Agent",
 "recorded_at": "<time>",
 "citation": "Four 2025 Form 1040-ES vouchers of $12,000 prepared with the 2024 return; payment confirmations not received.",
 "citation_ids": ["<c-1040es>"],
 "references": [
   {"id": "<ref-2024-estimates>", "kind": "prior_return", "label": "2024 Form 1040 — estimate worksheet",
    "detail": null, "citation_id": "<c-1040es>", "document_id": "<doc-2024-1040>", "page": null}],
 "unsupported": false, "suggestion_id": "<s-estimates>", "checkpoint_id": null, "issue_id": "<issue-estimates>"}
```
The issue row reads "Open issue: Obtain 2025 federal and NY estimated tax payment confirmations" and opens TAX-06.

**SHL-09 c. Human-edited** (viewer Kevin Osei). `PUT …/value` with `{value, value_kind, citation_note, seen_seq}`. The new version has `value_source: "human"`, `cause: "edit"`, `actor_kind: "human"` and `actor_name: "Kevin Osei"`, and its `citation` is Kevin's note ("Per client email Sep 9 — Jonah confirmed…"). The pill reads "Edited". An edit without a note fails the schema, and a stale `seen_seq` answers `409 {"detail": "field_changed"}`.

**SHL-09 d. Signed off.** Both ticks ("✓ KO · Sep 11", "✓ SI · Sep 14") are on the current hash, so both read `"stale": false`, and `flags` is empty.

**SHL-09 e. Uncited agent value.** The current version has `"citation": null`, `"citation_ids": []` and `"unsupported": true`, so the Citation row reads "No source cited" with the "Unsupported" pill. `allowed_actions` has no `field.sign_off`, and a tick answers `422 {"detail": "uncited_change"}` ("Add a reference before signing off").

**SHL-09 f. Collapsed Previous** is the same payload as a; the fold is client state.

**SHL-16 a. Checkpoint 6 proposed.** `GET /v1/checkpoints?target_type=tax_return&target_id=<feld-1040>&filter=all`. Checkpoint 6 came from the SHL-10 a proposal (`<k1-proposal>`), and Checkpoint 5 is current.
```json
{"target_type": "tax_return", "target_id": "<feld-1040>", "filter": "all",
 "items": [
   {"id": "<checkpoint-6>", "target_type": "tax_return", "target_id": "<feld-1040>", "seq": 6, "name": null, "starred": false,
    "author_kind": "agent", "author_user_id": null, "author_name": "Accrued Agent", "cause": "agent_run", "status": "proposed",
    "current": false, "summary": "K-1 treatment: Ridgeline", "created_at": "2026-09-14T14:18:00Z", "content_hash": "sha256:5e1d…a6f0",
    "proposal_id": "<k1-proposal>", "restored_from_id": null, "agent_run_id": "<run>", "decision": null,
    "allowed_actions": ["checkpoint.approve", "checkpoint.reject", "checkpoint.rename"]},
   {"id": "<checkpoint-5>", "target_type": "tax_return", "target_id": "<feld-1040>", "seq": 5, "name": null, "starred": false,
    "author_kind": "person", "author_user_id": "<kevin>", "author_name": "Kevin Osei", "cause": "human_edit", "status": "saved",
    "current": true, "summary": "Preparer review edits", "created_at": "2026-09-11T21:40:00Z", "content_hash": "sha256:41b9…0e7c",
    "proposal_id": null, "restored_from_id": null, "agent_run_id": null, "decision": null,
    "allowed_actions": ["checkpoint.rename"]},
   {"id": "<checkpoint-4>", "target_type": "tax_return", "target_id": "<feld-1040>", "seq": 4, "name": null, "starred": false,
    "author_kind": "agent", "author_user_id": null, "author_name": "Accrued Agent", "cause": "agent_run", "status": "approved",
    "current": false, "summary": "Corrected Halvard 1099-INT (2,190 → 2,310)", "created_at": "2026-09-10T19:12:00Z",
    "content_hash": "sha256:9a07…d318", "proposal_id": "<halvard-proposal>", "restored_from_id": null, "agent_run_id": "<run-halvard>",
    "decision": {"id": "<checkpoint-4-approval>", "decision": "approved", "reason": null, "decided_by_user_id": "<kevin>",
                 "decided_by_name": "Kevin Osei", "decided_at": "2026-09-10T19:12:00Z", "proposal_decision_id": "<halvard-approval>"},
    "allowed_actions": ["checkpoint.restore", "checkpoint.rename"]},
   {"id": "<checkpoint-3>", "target_type": "tax_return", "target_id": "<feld-1040>", "seq": 3, "name": null, "starred": false,
    "author_kind": "agent", "author_user_id": null, "author_name": "Accrued Agent", "cause": "agent_run", "status": "approved",
    "current": false, "summary": "Initial draft self-checked", "created_at": "2026-09-03T16:05:00Z", "content_hash": "sha256:2c66…81fa",
    "proposal_id": null, "restored_from_id": null, "agent_run_id": "<run-draft>", "decision": null,
    "allowed_actions": ["checkpoint.restore", "checkpoint.rename"]},
   {"id": "<checkpoint-2>", "target_type": "tax_return", "target_id": "<feld-1040>", "seq": 2, "name": null, "starred": false,
    "author_kind": "import", "author_user_id": null, "author_name": "Imported Return", "cause": "engine_import", "status": "saved",
    "current": false, "summary": "Imported from CCH Axcess 2025I:FeldJ:V3", "created_at": "2026-08-28T15:46:00Z",
    "content_hash": "sha256:b350…6e29", "proposal_id": null, "restored_from_id": null, "agent_run_id": null, "decision": null,
    "allowed_actions": ["checkpoint.restore", "checkpoint.rename"]},
   {"id": "<checkpoint-1>", "target_type": "tax_return", "target_id": "<feld-1040>", "seq": 1, "name": "Extension estimate (4868)",
    "starred": true, "author_kind": "person", "author_user_id": "<kevin>", "author_name": "Kevin Osei", "cause": "manual_save",
    "status": "saved", "current": false, "summary": null, "created_at": "2026-04-13T17:00:00Z", "content_hash": "sha256:0f8e…37d5",
    "proposal_id": null, "restored_from_id": null, "agent_run_id": null, "decision": null,
    "allowed_actions": ["checkpoint.restore", "checkpoint.rename"]}],
 "current_checkpoint_id": "<checkpoint-5>", "total": 6, "allowed_actions": ["checkpoint.create"]}
```
Checkpoint 3's card names no approver, so the example leaves its decision out. The named Checkpoint 1 shows "Checkpoint 1" as its second line.

`GET /v1/checkpoints/<checkpoint-6>` (`compare=previous`) has the steps and the diff. The diff is SHL-10 a's four rows. 307,900 leaves line 28A (k) and enters line 28A (h), so the net change to total income is 0, a tie. The QBI line is on a separate form.
```json
{"checkpoint": {"id": "<checkpoint-6>", "target_type": "tax_return", "target_id": "<feld-1040>", "seq": 6, "name": null, "starred": false,
                "author_kind": "agent", "author_user_id": null, "author_name": "Accrued Agent", "cause": "agent_run", "status": "proposed",
                "current": false, "summary": "K-1 treatment: Ridgeline", "created_at": "2026-09-14T14:18:00Z", "content_hash": "sha256:5e1d…a6f0",
                "proposal_id": "<k1-proposal>", "restored_from_id": null, "agent_run_id": "<run>", "decision": null,
                "allowed_actions": ["checkpoint.approve", "checkpoint.reject", "checkpoint.rename"]},
 "compare": "previous", "compared_to_id": "<checkpoint-5>",
 "steps": [
   {"kind": "analyzed", "title": "Analyzed the drafted return", "detail": "Read 11 worksheets and the 2024 return's Schedule E, p. 2.", "at": "2026-09-14T14:16:00Z"},
   {"kind": "analyzed", "title": "Analyzed the draft Ridgeline K-1 (pre-release)", "detail": "Boxes G, 2, 5, 18A, 19A and the box 20 Z statement.", "at": "2026-09-14T14:17:00Z"},
   {"kind": "updated_worksheet", "title": "Updated worksheet", "detail": "Federal › Income › Sch E, p 2 - Partnership Passthrough (K-1 1065) › Ridgeline", "at": "2026-09-14T14:17:00Z"},
   {"kind": "updated_worksheet", "title": "Updated worksheet", "detail": "Federal › Deductions › Form 8995-A — Qualified business income", "at": "2026-09-14T14:18:00Z"},
   {"kind": "skipped_worksheet", "title": "Skipped creating worksheet", "detail": "Form 8582 — no passive losses this year, so it isn't required.", "at": "2026-09-14T14:18:00Z"}],
 "diff": [
   {"field_key": "activity_classification.ridgeline", "label": "Activity classification · Ridgeline", "old": "Nonpassive", "new": "Passive", "cause": "K-1 box G; 2024 Sch E", "citation_ids": ["<c1>", "<c2>"]},
   {"field_key": "sch_e.p2.28a_k", "label": "Sch E p. 2 line 28A (k) Nonpassive income", "old": "307900", "new": null, "cause": "moved to (h)", "citation_ids": ["<c1>"]},
   {"field_key": "sch_e.p2.28a_h", "label": "Sch E p. 2 line 28A (h) Passive income", "old": null, "new": "307900", "cause": "K-1 box 2", "citation_ids": ["<c1>"]},
   {"field_key": "f8995a.p1.l1.ridgeline", "label": "Form 8995-A Part I line 1 · Ridgeline QBI", "old": null, "new": "307900", "cause": "K-1 box 20 Z", "citation_ids": ["<c3>"]}],
 "totals": [{"label": "Net change to total income", "value": "0", "ties": true}]}
```
The footer reads "Approving makes Checkpoint 6 current. The sync chip will read 'Out of sync' until the return is exported."

**SHL-16 b. Approved.** `POST /v1/checkpoints/<checkpoint-6>/approve` with `{"seen_hash": "sha256:5e1d…a6f0"}`, with the full digest on the wire. The response is Checkpoint 6 with `status: "approved"`, `current: true` and a decision by Samuel Ito at 9:26 AM (`2026-09-14T14:26:00Z`), whose `proposal_decision_id` is the SHL-10 approval of `<k1-proposal>`. Checkpoint 5 loses Current. `checkpoint.approved` carries the deltas, and the record header's sync chip (T-01) reads "Out of sync". The toast reads "Checkpoint 6 approved".

**SHL-16 c. Older checkpoint.** `GET /v1/checkpoints/<checkpoint-3>?compare=current` returns its steps ("Created worksheet Federal › Income › Wages (W-2)", "Created worksheet Sch E, p 2 › Ridgeline", "Self-check: 0 errors, 2 warnings") and the diff against current. `POST /v1/checkpoints/<checkpoint-3>/restore` answers 201 with Checkpoint 7: `{"seq": 7, "cause": "restore", "status": "saved", "restored_from_id": "<checkpoint-3>"}`. Nothing is deleted ("This creates Checkpoint 7 as a copy of Checkpoint 3.").

**SHL-16 d. Rename and star.** `PATCH /v1/checkpoints/<checkpoint-5>` with `{"name": "Before K-1 treatment", "starred": true}`.

**SHL-16 e. Rejected.** `POST /v1/checkpoints/<checkpoint-6>/reject` with `{"seen_hash": "sha256:5e1d…a6f0", "reason": "Wait for final K-1"}`. The card reads "Rejected" and "Samuel Ito · reason: Wait for final K-1".

**SHL-16 f. Empty** (the Calloway 1041). The history is `{"target_type": "tax_return", "target_id": "<calloway-1041>", "filter": "all", "items": [], "current_checkpoint_id": null, "total": 0, "allowed_actions": ["checkpoint.create"]}`, so the drawer shows "No checkpoints yet." with "Save checkpoint…".

**SHL-15 a. Set fix instructions** (viewer Kevin Osei). `GET /v1/issues/<issue-18a>`, Feld issue 3 of 4. The agent's explanation (SHL-15 d) is already pinned to it.
```json
{"issue": {"id": "<issue-18a>", "engagement_id": "<feld>", "work_item_id": "<feld-1040>",
           "record": {"type": "tax_return", "id": "<feld-1040>"}, "kind": "missing_information", "priority": "high",
           "status": "open", "instructions_required": true, "assignee_user_id": null, "assignee_name": null,
           "assignee_agent": true, "blocks": [], "link_count": 2, "version": 1, "created_at": "<time>",
           "allowed_actions": ["issue.update", "issue.resolve", "fix_instruction.set", "issue.explain"]},
 "record_label": "2025 Form 1040 · Jonah & Claire Feld",
 "title": "Source K-1 box 18A 'Tax-exempt interest' is not on the worksheet",
 "internal_note": null, "client_wording": null, "client_contact": null,
 "links": [
   {"kind": "file", "label": "Ridgeline_2025_K1_JonahFeld_DRAFT.pdf", "target_type": "document", "target_id": "<doc-ridgeline-k1>", "anchor": null},
   {"kind": "form_field", "label": "Form 1040 · line 2a", "target_type": "tax_return", "target_id": "<feld-1040>", "anchor": "f1040.l2a"}],
 "suggestion": {"text": "Add 1,550 from the draft Ridgeline K-1 box 18A to Form 1040 line 2a. Check the K-1 statement for the state of the bonds and add any non-New York portion to IT-201 line 20. Mark both values as draft until Ridgeline releases final K-1s.",
                "agent_run_id": "<run-18a>", "suggested_at": "<time>"},
 "fix_instructions": null, "fix_run": null,
 "explanations": [
   {"id": "<explain-18a>", "text": "Line 2a is informational federally, but New York adds interest on other states' bonds back on IT-201 line 20. Leaving it out would understate New York income by up to $1,550, and the IRS matches K-1 reporting to the return.",
    "agent_run_id": "<run-explain-18a>", "explained_at": "2026-09-14T14:22:00Z",
    "citations": [{"citation_id": "<c-k1-18a>", "label": "K-1 box 18A"}, {"citation_id": "<c-k1-statement>", "label": "K-1 statement p. 3"},
                  {"citation_id": "<c-it201>", "label": "IT-201 instructions, line 20"}],
    "pinned": true}],
 "request_item_id": null, "events": []}
```
"Use suggestion", plus Kevin's constraint, then "Set Fix Instructions":
```json
{"seen_version": 1, "scope": "this_issue",
 "text": "Add 1,550 from the draft Ridgeline K-1 box 18A to Form 1040 line 2a. Check the K-1 statement for the state of the bonds and add any non-New York portion to IT-201 line 20. Mark both values as draft until Ridgeline releases final K-1s.\nDon't change taxable interest on line 2b (6,910)."}
```
- The 202 is `{"issue_id": "<issue-18a>", "agent_run_id": "<run-fix-18a>", "status": "in_progress"}`. With no runner registered it answers `409 {"detail": "fix_runner_unavailable"}`, and the sheet shows the agents-off state.
- **a-prime.** The detail's `fix_run` is `{"agent_run_id": "<run-fix-18a>", "label": "Adding 1,550 to Form 1040 line 2a", "status": "running", "proposal_id": null}`, and the queue row reads "In progress — agent fixing".
- **a-double-prime.** The run ends in a proposal, so `fix_run.proposal_id` is set, and Accept opens SHL-10 b. There the line 2a suggestion adopts the same 1,550 (part 2).

**SHL-15 b. New audit issue** (viewer Ana Cruz, Northwind). `POST /v1/issues` from cells F12:F15 of EBP-04, four rows for the four participants:
```json
{"record_type": "workpaper", "record_id": "<ebp-04>", "kind": "waiting_on_client", "priority": "high",
 "title": "Opt-out elections missing for 4 auto-enrolled participants who are not deferring",
 "internal_note": "The plan is a QACA with 6% default deferral. Four eligible participants had no 2025 deferrals and no opt-out election on file. If none exists, this is a missed-deferral failure to correct under EPCRS (start the correct deferrals, notify the participants and fund any missed QACA safe-harbor match; a QNEC for the missed deferrals may be 0% under the auto-enrollment safe harbor if corrected in time); evaluate as a control exception in AUD-15.",
 "client_wording": "Four employees were automatically enrolled in the 401(k) but had no contributions in 2025. Please upload their signed opt-out forms, or let us know if none exist. The list is attached.",
 "client_contact_id": "<dana>", "assignee_user_id": "<ana>", "assignee_agent": false,
 "links": [{"kind": "cell_range", "target_type": "workpaper", "target_id": "<ebp-04>", "anchor": "F12:F15"},
           {"kind": "file", "target_type": "document", "target_id": "<northwind-census>", "anchor": null}],
 "blocks": []}
```
"Create & send to client" then posts `POST /v1/issues/<opt-out-issue>/send-to-client` with an `Idempotency-Key` and `{"seen_version": 1, "client_wording": "Four employees were automatically enrolled in the 401(k) but had no contributions in 2025. Please upload their signed opt-out forms, or let us know if none exist. The list is attached.", "contact_id": "<dana>", "due_on": null}`. One request item is created in Dana Kowalski's portal (POR-04), and `request_item_id` is set. The internal note never leaves the firm.

**SHL-15 c. New issue from a field flag** (viewer Samuel Ito). Feld Issues goes from 4 to 5 (`total` on `GET /v1/issues?record_type=tax_return&record_id=<feld-1040>`).
```json
{"record_type": "tax_return", "record_id": "<feld-1040>", "kind": "review_point",
 "title": "Confirm Ridgeline K-1 amounts against the final K-1 before export",
 "assignee_user_id": "<kevin>", "assignee_agent": false,
 "links": [{"kind": "form_field", "target_type": "tax_return", "target_id": "<feld-1040>", "anchor": "f1040.l2b"}]}
```
The chip reads "Ridgeline K-1 box 5 → Form 1040 line 2b".

**SHL-15 d. Explain.** `POST /v1/issues/<issue-18a>/explanations` answers 202 `{"issue_id": "<issue-18a>", "agent_run_id": "<run-explain-18a>"}`. The explanation arrives on the detail (a, above) with its three citation chips. It is read-only and decides nothing.

**SHL-15 e. Bulk instructions.** `POST /v1/issues/fix-instructions:bulk` with the two Missing information issues (`<issue-estimates>` and `<issue-18a>`, each with its `seen_version`) and one shared text. The scope is locked to the selection, so each issue gets one sealed instruction with scope `this_issue`. The response has two `results`, and `accepted` plus `excluded` is 2. The CTA reads "Set Fix Instructions for 2".

## 9. Consumer contract tests
P-04-T09 (2026-10-22). Both suites run in the provider's stage 2 (`make check`: `ci-contracts` and `ci-frontend`). They fail if a field the artboards need is removed, renamed or retagged.

- `backend/tests/contracts/review_grammar/` (pytest against the stubs):
  - `test_c3_stubs.py`: every route's matrix action, and 404 off and 501 on through each handler; agent and system denied on every resolution, decision and sign-off action; the status enums against `status-vocabulary.yaml`; the CHECK lists in migrations 0093 to 0095 against the wire; every field classified.
  - `test_c3_shl10_proposals.py`, `test_c3_shl11_decision_cards.py` and `test_c3_shl12_sign_offs.py`: per artboard, the fields with their classification tags, and the §8 examples validated as written (placeholders swapped for UUIDs).
  - The figures foot as `Decimal`: Trial Balance v1 14 of 14 cited; Northwind materiality 168,100 / 252,200 / PM 189,150 / CT 12,610 and v3 252,900 ($700); Feld K-1 net change 0; AJE-05 14,900.00.
- `apps/web/src/fixtures/contracts/review-grammar.test.ts` (vitest): one frame per artboard, typed with the generated client and checked against `openapi.json` at run time; figures foot in bigint.
- Unique names: the operation ids and the C3 component names (`AgentProposalOut`, `AgentSuggestionOut`, `ReviewNoteDetailOut`, `CardDecisionOut`, `CardDecideIn`, TASK-422) are asserted, so a collision cannot rename a frozen type again (#284).
- One strict xfail, to clear before the freeze: #285 (decision-card figures and the agent's reasons should be Restricted).

Part 3 (P-04-T12, 2026-10-23), in the same two suites:

- `test_c3_stub3.py` covers stub 3 as a whole:
  - the 23 routes declare their one matrix action, with 404 and 501 in their responses, the 202s on the run starts and the 201s on new rows;
  - each handler, called directly, answers 404 with `review.grammar_api` off and 501 with it on;
  - send to client requires `Idempotency-Key`;
  - every part 3 write and resolution denies `agent` and `system` explicitly, and the agent holds only `checkpoint.propose`;
  - the QC `reviewer` role writes only an issue, an Explain request and a field tick;
  - `IssueStatus`, `IssueSeverityStatus`, `CheckpointStatus`, `AgentRunStatus` and `ReviewNoteStatus` are the registry's stored codes, and `current`, `stale`, `unsupported` and every `field_value` word are derived;
  - the CHECK lists of migrations 0093 and 0094 equal the wire literals, and the human-only and citation-note constraints exist;
  - every part 3 field is classified;
  - the operation ids and component names are unique, and the stub 1 and 2 paths are untouched.
- `test_c3_shl09_field_provenance.py`, `test_c3_shl15_issues.py` and `test_c3_shl16_checkpoints.py` hold, per artboard, the fields with their classification tags and the part 3 examples validated as written.
- The figures foot as `Decimal`:
  - Halvard 2,190 → 2,310, with Box 1 at 2,310.00;
  - the estimate, 4 × 12,000 = 48,000;
  - Checkpoint 6's diff is SHL-10 a's four rows, and the net change to total income is 0;
  - the fix run's 1,550 is the line 2a suggestion's;
  - F12:F15 is four participants.
- The vitest frames are SHL-09 a to f, SHL-15 a, a-prime, a-double-prime, b and d (with c and e as requests), and SHL-16 a, b, d, e and f (with c's restore). Each is typed with the generated client and checked against `openapi.json`.
- Stub 3 is recorded in `docs/contracts/README.md` as an additive extension of the C3 v1 schema (handshake rule 5).

## 10. Versioning
Additive changes go in place. Breaking changes ship as v2 with one sprint of overlap.

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | (S3, Fri Dec 11, 2026) | | 2026-10-22: part 1 stub (P-04-T07): sign-offs, review notes and human gates. 2026-10-22: part 2 stub (P-04-T08): decision cards (`review`), proposals and suggestions (`agents`). 2026-10-22: consumer tests (P-04-T09); the schema freeze is scheduled for Fri Dec 11, 2026 with them as the gate. 2026-10-23: part 3 stub (P-04-T11): issues and fix instructions, checkpoints and field provenance, additive (new models and routes beside the old; no part 1 or 2 shape changed). 2026-10-23: part 3 consumer tests (P-04-T12); the QC `reviewer` cells on part 3 writes were narrowed (DEC-145) |

## 11. Open points
- **Level actions.** The level actions keep their SPEC-308 names rather than `sign_off.l1` to `l5` (DEC-135).
- **Note bodies.** Note bodies are Restricted, so the list carries none. A detail route, `GET /v1/review-notes/{note_id}`, is added beyond the plan's table. Each body read is then one access event.
- **`sign_off.eqr` cell.** The row allows `reviewer` (SPEC-308). The F-03-T23 role `eqr_reviewer` is added to the reads and to `sign_off.create`. Moving `sign_off.eqr` to `eqr_reviewer` is P-04-T15's, with the generated deny tests.
- **Flag expiry.** `review.grammar_api` was renewed on 2026-10-23 to expire 2027-04-21 under DEC-137 (F-03-T37), after the Jan 1 to Apr 20 window. Part 3 reuses it, so it covers every C3 route.
- **Part 2 module split.** Decision cards are `review`'s (`review/contract.py`, `review.yaml`). Proposals and suggestions are `agents`' (`agents/contract.py`, `agents.yaml`), per ADR-160 clause 1 and ADR-161. One flag, `review.grammar_api`, covers both, and the agents routes read it from the kernel flag registry.
- **`proposal.create`.** It is added for the agent through `task_scope` (as `suggestion.create`), for `agents.api.create_proposal`. `decision_card.raise` arrives with its service function in P-04-T23.
- **Human-only audit register (Q-02-T17).** `decision.decided`, `proposal.approved` and `suggestion.adopted` join `docs/architecture/human-only-actions.yaml` with their services (P-04-T23, T24). That change needs its migration.
- **Part 3 matrix (DEC-145).** The rows carry role cells now. The reviewer and preparer function conditions arrive with P-04-T15, because a condition only narrows a row (DEC-132). None of the part 3 rows is marked `independence: required`: the plan names independence only for the sign-off levels, and SHL-15 and SHL-16 are mostly tax returns, where it does not apply. P-04-T15 revisits this for attest targets with the generated tests.
- **Part 3 lists.** Issue titles are sealed and Restricted, so `GET /v1/issues` rows carry no title. The queue screens (TAX-06, TXP-10, AUD-15) read the detail, or ask their own contract for a queue read. A checkpoint's summary may carry return figures, so the checkpoints of one target are a history read (`CheckpointHistoryOut`), not the list envelope.
- **Explain.** `POST /v1/issues/{issue_id}/explanations` (`issue.explain`) is added beyond the plan's table for SHL-15 d. It answers `fix_runner_unavailable` when no runner is registered, because the fix runner slot also explains.
