---
id: ADR-161
title: Suggestions, proposals, approval grants and Undo as a compensating event; the policy actor is dormant
status: accepted
date: 2026-10-22
deciders: notanaskhan, ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Three gaps meet here (chapter 09 P-35, DEC-24, DEC-28):

1. **No generic suggestion store.** Each agent output has its own typed table (`screening_results`, `upload_reviews`, `inbox_match_proposals`, `guidance_drafts`). The approval screen SHL-10, field adoption (C-31) and every later specialist need one shape: a proposed value for one target, grouped into a change set a person approves.
2. **No authority for writes after approval.** Some effects run after the human decision: a client email, an export, an envelope, a ledger post. Nothing today proves that the write a worker performs is the one a named person approved, or that the person still holds the right when it runs.
3. **The design's 10-second Undo clashes with insert-only decisions.** Chapter 04 (FE-13) kept the decision in the browser for 10 s and committed it afterwards. A closed tab then loses the decision, and other viewers see stale state. The decision tables are insert-only (ADR-004, ADR-007), so Undo cannot delete a row.

Chapter 09 conflict X-2 and DEC-24 chose a server-side compensating event plus an effect hold; DEC-28 chose generic tables. This ADR records both as proposal P-35 (AG-08), from chapter 03 sections 3.7.3 and 4.7. The plan's chapters call it "ADR-126"; the plan's 116-130 pre-allocation was superseded (SPEC-046 AC-4), so P-35 takes ADR-161 (`docs/adr/backlog.md`).

## Decision
1. **Suggestions.** `agents.suggestions` holds one proposed value for one target and field (`proposed_value` typed, rationale as AgentText, `citation_ids`, `confidence`, `agent_run_id`). Status changes only to `pending`, `adopted`, `edited`, `dismissed`, `superseded` or `expired`; the human act is an insert-only, human-only `suggestion_decisions` row (`adopted`, `edited`, `dismissed`, `undone`). Adopting calls the owner's registered applier, which writes `field_value_versions` with `cause = 'suggestion_adopted'` through `review.api.record_value` (ADR-160 clause 10).
2. **Proposals.** `agents.proposals` is a change set (registered `kind`: `field_change_set`, `conclusion`, `entry_batch`, ...) with insert-only `proposal_rows` (before, after, cause, citations, `unsupported`) and an optional `policy_eval` (policy id, version, `within_threshold` or `review_required`). The human act is an insert-only, human-only `proposal_decisions` row (`approved`, `approved_with_edits`, `rejected`, `routed`, `follow_up`, `undone`). Server rules: approval is refused with `422 uncited_change` while any row lacks a verified citation; a stale `seen_version` answers `409 proposal_changed`; an edit requires a citation note. Agents create suggestions and proposals only through `agents.api.create_suggestion` and `create_proposal` within their task scope (ADR-025).
3. **Typed tables stay.** `screening_results`, `upload_reviews`, `inbox_match_proposals` and `guidance_drafts` are not migrated. Typed adapters project them as proposals for SHL-10, and their pending items project into `human_gates` (ADR-160 clause 11). An adapter approval writes exactly the row the existing path writes (for example the REVIEW-001 `review_decisions` row).
4. **Approval grants.** `identity.approval_grants(subject_ref, action, approver_user_id, payload_hash, not_before, expires_at, used_at, voided_at)` is single-use authority for any write that runs after approval: client-visible sends and notices, exports, envelopes, ledger posts. Only `used_at` and `voided_at` are updatable. `identity.api.consume_grant` is **the single gate**: one guarded UPDATE (`used_at IS NULL AND voided_at IS NULL AND now >= not_before AND now < expires_at`) after re-checking that the approver still holds `action`, and the payload hash must match what was approved. Effects are dispatched by the kernel's `not_before` outbox delivery (client email) or by the `effect_hold` Temporal workflow (exports, posts); both call `consume_grant` and send nothing when it refuses. This is layer 5 of the human-only pattern (ADR-160 clause 12).
5. **The decision is written at once.** A human decision row is committed when the person acts, so it survives a closed tab and others see it immediately. The UI is never optimistic about a human gate: the decided line comes from the server response.
6. **Undo is a compensating event.** Undo inside 10 seconds writes a `*.undone` row (for example `proposal.undone`, with `undoes_decision_id`) by the same person, voids the decision's grant and reverses the decision's own internal effect in the same unit of work (an adapter approval that wrote a review decision also calls `evidence.api.undo_review_decision`). Undo after the window answers `409 undo_window_closed`; Undo after an effect has started (grant consumed) answers `409 effect_started`. The window is measured on `kernel.clock` and backstopped by a database trigger that refuses an `undone` row for a decision whose grant is consumed or whose window has passed. Nothing is deleted. Any effect that leaves the firm is held by a grant with `not_before = decided_at + 10 s`. One Undo contract covers evidence decisions (P-01), proposals (P-04) and client sends (P-06), proved by one shared conformance suite every Undo route registers in. This supersedes chapter 04's browser-side deferred commit (FE-13, section 7.5).
7. **The policy actor is dormant.** `policy` is added to the actor-kind vocabulary so the schema need not change later, and it is locked off: the CHECK `fvv_policy_dormant` on `field_value_versions`, the human-only CHECKs on every decision table and the matrix refuse it. Season 1 ships named-human batch approval ("Approved by ‹person› under ‹policy› vN"); no surface attributes an approval to "Policy" or to the agent while P-08 is dormant. Enabling it needs an accepted P-08 ADR (DEC-53) and a migration, no earlier than Q2 2027, and it can never apply to sign-offs, decisions, release, return approval, sends, posts or exports, or to attest clients.

Solo-edition reading: "accepted by both founders" is recorded as acceptance with both handles in `deciders` (`docs/plan/AMENDMENT-solo.md`); there was no meeting.

## Options considered
### Option A: generic suggestions and proposals, approval grants, server compensating Undo - chosen
- Pros: one approval surface for every specialist; post-approval writes carry provable, revocable, single-use authority; a decision is never lost and is visible at once; insert-only tables stay insert-only.
- Cons: two dispatchers that must both call `consume_grant`; every client-visible effect is delayed 10 s; adapters to maintain for the typed tables.

### Option B: per-feature proposal tables (DEC-28 a)
- Cons: every specialist reinvents approve, reject, route, edit and Undo; Home must union them.
- Why rejected: DEC-28 chose (b).

### Option C: deferred commit in the browser (DEC-24 a, chapter 04 FE-13)
- Pros: no server Undo endpoint.
- Cons: a closed tab loses the decision; other viewers see stale state; an effect cannot be held server-side.
- Why rejected: DEC-24 chose (b); chapter 09 X-2.

## Consequences
**Positive**
- Every effect that leaves the firm can be traced to one grant, one approver and one payload hash.
- Undo has one meaning everywhere and is tested once.

**Negative / costs accepted**
- Client-visible sends wait at least 10 s after approval.
- Adapters must keep the typed tables and the proposal projection equivalent (an equivalence test).

**Follow-up work created**
- **Schema:** `NNNN_agent_suggestions_proposals` with the undo trigger (P-04-T05); `NNNN_approval_grants` (P-04-T10).
- **Services:** proposal routes and adapters (P-04-T24, T25); Undo and the effect hold, including the `effect_hold` workflow with a replay history (P-04-T29); the kernel `not_before` delivery (P-06-T06); evidence Undo (P-01-T13).
- **Tests:** the shared C3 Undo conformance suite `backend/tests/contracts/test_undo_contract.py` (P-04-T13); Undo and effect-hold acceptance tests (P-04-T33).
- **Frontend:** `useGate` and `toast.undoable` call only the compensating command (P-04-T40).

## Enforcement
- [ ] Lint rule: `PROPOSAL-001` names the only files that may call the proposal decision function.
- [ ] Test: both dispatchers (kernel `not_before` delivery and `effect_hold`) send nothing when `consume_grant` refuses (voided, consumed, early or expired grant).
- [ ] Test: Undo conformance suite (compensating row, same actor, 10 s on `kernel.clock`, `409 undo_window_closed` and `effect_started`, a voided grant sends nothing); `422 uncited_change`; generated I-AGENT-NEVER for `proposal.*` and `suggestion.resolve`; a `policy` actor is refused by every decision table.
- [ ] Test: the undo trigger refuses an `undone` row after the window or after the grant is consumed.
- [ ] Reviewer agent checklist item: no optimistic gate UI; no deleted or updated decision row; no external write without a grant.

## Guidance for agents
Write the decision now; hold the effect; undo by appending.

**Do**
```
grant = await identity.api.issue_grant(ctx, subject, action, payload_hash=h, not_before=now + 10s)
await outbox.emit("message.send", ..., not_before=grant.not_before, approval_grant_id=grant.id)
```

**Don't**
```
DELETE FROM proposal_decisions WHERE id = :id              # Undo is a compensating row
await ses.send(...)                                         # an effect without consume_grant
```

## Revisit when
P-08 (policy principal) is accepted; or a regulated effect needs a window longer than 10 s; or a third dispatcher is proposed.

## Related
- P-ID: P-35 (DEC-24, DEC-28; AG-08), drafted by P-04-T01. Plan alias "ADR-126" maps to ADR-161 (`docs/adr/backlog.md`).
- Amends (by extension, without editing them): ADR-005 (humans decide; grants carry their authority to later writes), ADR-025 (agents create proposals within task scope only), ADR-007 (Undo is an appended event), ADR-054 (a proposal is the handoff form for change sets).
- Companion: ADR-160 (review grammar; five-layer pattern). Related: ADR-139 (`Idempotency-Key` on external effects), ADR-157 (kill switches stop dispatchers).
- Docs: `docs/plan/03-backend-architecture.md` sections 3.7.3 and 4.7; `docs/plan/09-decisions-adrs.md` X-2, DEC-24, DEC-28, P-35; `docs/plan/epics/P-04.md` F5.
