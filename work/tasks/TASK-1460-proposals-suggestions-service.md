---
id: TASK-1460
title: Proposals and suggestions service, approve, approve with edits, reject, route, follow-up, adopt and dismiss (P-04-T24)
spec: SPEC-360
acceptance_criteria: [AC-4]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T24
branch: s12-review
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The proposal and suggestion routes (`agents/contract.py`, C3 part 2) answer 501. Serve them:
approve, approve with edits (a citation note per edit), reject with a reason code, route to a
named approver, a recorded follow-up, and suggestion adopt and dismiss. 422 `uncited_change`
through C4 verification, 409 `proposal_changed`, registered appliers that write
`field_value_versions` (cause `suggestion_adopted`, or `edit` for an edited row) and link the
proposal's checkpoint, and the `PROPOSAL-001` rule. Acceptance: "A proposal with one unsupported
row cannot be approved until that row is removed or cited, and approval records Proposal approved
by Samuel Ito with one field version per row."

## Plan
- **Migration 0230** (`0230_proposal_decision_guards`, down 0220): the app may insert
  `proposal_decisions.id` and `suggestion_decisions.id` (sealed notes bind to the row); a
  `proposals.state` guard (pending -> approved, approved_with_edits or rejected only with the
  acting person's decision row of that kind written in this transaction; nothing else for the
  app) and a `suggestions.status` guard (pending -> adopted, edited or dismissed likewise, or ->
  superseded with the proposal's approval or rejection); `decided_by` is the transaction actor
  on both decision tables (CHECK).
- **Migration 0231** (`0231_proposal_human_only`): `abacus_human_only_actions()` gains
  `proposal.approved`, `proposal.approved_with_edits`, `proposal.rejected`, `proposal.routed`,
  `suggestion.adopted`, `suggestion.edited`, `suggestion.dismissed`; the YAML register and the
  generated `_human_only_actions.py` follow.
- **review.api.record_value** (`review/field_values.py`): the write path for
  `field_value_versions` inside the caller's unit of work: next `seq` under a per-field
  transaction lock, typed value `{t, v}`, a human edit's citation note sealed to
  (target, field, seq), `field.value_recorded` outbox. Provenance reads, ticks and FIELD-001 stay
  P-04-T35's.
- **Slots** (`agents/proposal_slots.py`): `register_suggestion_applier(target_type, applier)`
  (the target owner's, in the approving unit of work; it calls `record_value`) and
  `register_change_set_applier(kind, applier)` for kinds other than `field_change_set`. Fail
  closed: no applier answers 503 before anything is written.
- **Service** (`agents/proposals.py`): `create_proposal` and `create_suggestion` (agent through
  `task_scope`, `proposal.create` / `suggestion.create`; rows' `unsupported` computed by C4),
  `proposal_view` (the C3 projection with `allowed_actions`), `approve`, `reject`, `route`,
  `follow_up`, `adopt`, `dismiss`. Order of refusals: non-person 403; matrix; 409
  `proposal_changed` (stale `seen_version`, or the proposal no longer pending); 403
  `forbidden {routed_to}` over the viewer's threshold; 422 `uncited_change {rows}` (stored
  unsupported or no longer verified by C4, and not edited with a citation note); 422
  `proposal_invalid` for an unknown row or a malformed edit. Every write is one unit of work with
  its audit event (`proposal.*`, `suggestion.*`) and outbox (`proposal.decided`,
  `proposal.routed`, `suggestion.resolved`).
- **C4**: `evidence.api.supported_citations(tenant, engagement_id, ids)`: verified, shown, on the
  engagement and with no moved, broken or relinked event.
- **Matrix**: rows exist (P-04-T08). **PROPOSAL-001**: only `agents/proposals.py`,
  `agents/proposal_adapters.py` and `agents/contract.py` name the decision functions.
- **Tests first**: `tests/integration/test_p04t24_proposals.py` (Feld K-1 shaped change set on a
  test target with a registered applier; Samuel Ito approves; the fifth uncited row; edits; route
  over threshold; reject; follow-up; adopt and dismiss; agent and system refused).
- **Rollback**: revert; downgrade 0231 then 0230.

## Progress log
- 2026-10-27: planned.
- 2026-10-27: built (acceptance tests first; run in the end-of-batch targeted pass). Claude Code restarted mid-build; the worktree was saved as WIP commit 743d43fa and the build resumed from it. Decisions DEC-600 to DEC-608; migrations 0230, 0231; SPEC-360 gains AC-4 to AC-7.
- 2026-10-27: mistakes found by the tests, for a lint rule: nullable JSONB columns must be `JSONB(none_as_null=True)` (a Python None became JSON `null` and failed the `jsonb_typeof` CHECKs), and a `uuid[]` bind through `text()` takes a list, not a `{...}` string.
- 2026-10-27: security review fix round (PASS WITH FIXES): H, M1 to M6 and the lows fixed (DEC-609); migration 0232; matrix action `proposal.decide_change_set`.
