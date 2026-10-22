---
id: ADR-160
title: Review grammar - sign-offs, review notes, issues, decision cards, checkpoints and field history in one red review module
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
About 60% of the P0 screens mount a human judgement on prepared work: sign off a workpaper, raise a review note on a cell, decide materiality, approve an import checkpoint, flag a field, raise an issue. The repo has no general model for any of these. It has `review_decisions` (evidence and requests only, migration 0015), three fieldwork-only tables (`item_signoffs`, `review_notes`, `workpaper_signatures`) and nothing for decisions, checkpoints or field history. Each service line would otherwise grow its own sign-off rules, its own staleness test and its own segregation check, on the records an inspector reads first (AU-C 230). These rows must have their final shape before real data arrives (RK-16): after Jun 1, 2027 the schema may only expand.

DEC-36 chose a new red `review` module (option b) over generalising `review_decisions` (option a). This ADR records that choice as proposal P-07, from chapter 03 sections 3.7 and 4.7 and epic P-04. ADR-134 already binds fieldwork to this grammar; this ADR is the grammar it rides. The plan's chapters call this ADR "ADR-133"; that number was minted for product naming, so P-07 takes ADR-160 (`docs/adr/backlog.md`).

## Decision
1. **One red module.** `backend/src/abacus/modules/review` owns every sign-off, review note, issue, decision card, decision, checkpoint, field value version and the `human_gates` projection. No other module creates a table for these acts (ADR-134 clause 1, generalised). `review` imports only `identity`, `platform` and `engagements`; `agents` may import `review`, never the reverse. Service lines reach the engine only through registration slots: `register_reviewable` (target type, content hash, version, preparers, required levels), `register_decision_kind` (options computed by code, reserved role, MFA rule), `register_gate_kind`, `register_field_owner` and `register_fix_runner`. An unregistered kind is refused (`503` on routes, `RegistrationMissing` in services), as ADR-106 does for other slots.
2. **Sign-offs.** `sign_offs` is insert-only and human-only: `kind in {ladder, field_tick, final_approval}`, `level in {L1_preparer, L2_reviewer, L3_manager, L4_partner, L5_eqr}`, the signer, initials, role and function at signing, `content_hash`, `version_no`, `statement_version`, `adopted_run_id`, `independence_checked_at`. Level names are fixed; which levels a target requires comes from firm standards (`ReviewableFacts.required_levels`, K-02), with platform defaults until then.
3. **Content hash and computed staleness.** The owner computes `content_hash = sha256(JCS(canonical_json({target_type, target_id, version_no, fields: sorted (field_key, value_string), citation_ids: sorted})))` (RFC 8785) and keeps it current on the reviewable row in the same unit of work as any change. A sign-off write carries `seen_hash`; a mismatch answers `409 content_changed`. A sign-off is stale when its hash differs from the target's current hash. **There is no stale column and no sign-off row is ever updated**; re-signing writes a new row. A consumer of `<owner>.version_created` emits `sign_off.went_stale`.
4. **Invariants R-SO-1 to R-SO-8** are enforced in `review.service` and a property suite: only a live human signs (R-SO-1); level eligibility from work-item function plus membership level, L4 needs the engagement partner or the `signer` function, L5 needs `eqr_reviewer` (R-SO-2, `403 level_not_permitted`); segregation, so the preparer never signs L2 or L3 on the same target, the EQR never signs L1 to L4 on that engagement and the engagement partner is never EQR on their own engagement (R-SO-3, `409 segregation`); open review notes block L2 and above (R-SO-4, `409 open_review_notes`); a missing independence confirmation blocks (R-SO-5, gate G2, `409 independence_pending`); empty required fields or uncited values block (R-SO-6, `409 incomplete`, `422 uncited_change`); bulk sign-off is for reviewers, per item and atomic per item (R-SO-7); an L1 on agent work records `adopted_run_id` and adopts that run's pending suggestions, rendered "Performed by Agent run #n under the direction of ‹person› · adopted by ‹initials›" (R-SO-8).
5. **Field ticks are sign-offs; field flags are review notes.** A tick on a field (SHL-09 "✓ KO") is a `sign_offs` row with `kind = 'field_tick'` at L1 or L2 on a `field` target. A flag ("⚑ SI") is a review note anchored to that field. One staleness rule covers ladders and ticks. An uncited agent value reads "Unsupported" and cannot be ticked.
6. **Review notes.** `review_notes` (only `status` is updatable) plus insert-only `review_note_events`; the anchor is a cell address, field key, section or document region; bodies are sealed. `cleared` requires a human. Open notes block L2 and above. Comments never block (DEC-29, ADR-109).
7. **Issues.** One cross-module `issues` service with `issue_events` and `issue_links`, deduplicated on `(work_item_id, source_ref)`. `blocks` names what an open issue stops (`final_approval`, `export`, `release`, `sign_off`). Internal note and client wording are separate sealed columns; only `send-to-client` creates a client-visible request item, and it carries only the client wording (ADR-111). Resolve, verify, reopen and not-applicable are human-only. Every agent fix ends in a proposal a person accepts (DEC-53, DF-13); there is no direct-edit mode.
8. **Decision cards.** One object (chapter 09 X-13): `decision_cards` raised through `review.api.raise_decision_card` (agents may raise; there is no `decision_requests` table) and insert-only, human-only `decisions`. Options are computed by the owner's provider, never by a model (ADR-050). A rationale is required (`422 rationale_required`); a stale card version answers `409 recommendation_changed`; the kind's provider declares whether recent MFA is required (`403 mfa_required`). Only the reserved role decides. An agent recommendation is a suggestion (`recommendation_suggestion_id`) and is never worded as the decider. A reassessment with no change is a new version of the same card; a changed outcome raises a superseding card and marks the old one "Superseded by vN".
9. **Checkpoints.** `checkpoints`, insert-only `checkpoint_diffs` (old, new, cause, citations, amount deltas) and insert-only, human-only `checkpoint_decisions`. Diffs are computed by code. `author_kind in {agent, person, import}`; an engine import lands as a checkpoint pending approval. "Current" is a derived tag, not a stored status. Restore creates a new checkpoint as a copy; nothing is deleted. Approving a checkpoint linked to a proposal is the same decision as approving that proposal (ADR-161).
10. **Field value history.** `field_value_versions` is insert-only and the provenance ledger for every cell and field: typed values (decimals as strings), `value_source`, `cause`, actor columns with `on_behalf_of_user_id`, `suggestion_id`, `checkpoint_id`, `citation_ids`. A human edit requires a sealed citation note. `review.api.record_value` is the only write path. The `policy` source and actor are refused by CHECK `fvv_policy_dormant` until a migration under an accepted P-08 ADR drops it (DEC-53; ADR-161 clause 7).
11. **Human-gate projection.** `human_gates` (kinds `decision`, `sign_off_request`, `proposal`, `send`, `final_approval`, `export`, `release`) is rebuilt from outbox events, idempotent on `event_id`, and rebuildable by an admin command. Home tiles and queues read only this projection. The repo's typed proposal tables project into it as `proposal` gates (DEC-28).
12. **The human-only enforcement pattern (chapter 03 section 4.7).** Every resolution action in this grammar (sign-off L1 to L5, `decision.decide`, proposal and suggestion resolution, `checkpoint.approve`, issue resolution, note clearing, field ticks) uses all five layers: (1) the matrix denies `agent`, `system` and `support`; (2) `identity.require_live_human(ctx)` is the first line of the service function; (3) the decision table has `CHECK (actor_kind = 'human')` with the actor bound to the transaction GUCs by a SECURITY DEFINER trigger (the `0015_review_decisions` pattern); (4) a static rule per object (`SIGNOFF-001`, `DECISION-001`, `PROPOSAL-001`, `CHECKPOINT-001`, `ISSUE-001`, `FIELD-001`) names the only files that may call the decision function; (5) any write that runs after approval consumes an approval grant (ADR-161). I-AGENT-NEVER is generated from the matrix for every such action. Client principals can read none of these records.
13. **Cell addresses and workbook formulas.** Designed workpapers get deterministic cell addresses mirroring the Open-in-Excel layout (`EBP-04!C14`), used as anchors and citation locators. Firm workbook formulas use a closed expression grammar (cell references, `SUM`, `ROUND`, `IF`, `MIN`, `MAX`) parsed by our own parser and evaluated as a dependency graph; nothing ever uses `eval`. ADR-110's rule that uploaded spreadsheet formulas are never evaluated is unchanged: these are firm cells, not client files.

Solo-edition reading: "accepted by both founders" is recorded as acceptance with both handles in `deciders` (`docs/plan/AMENDMENT-solo.md`); there was no meeting.

## Options considered
### Option A: a new red `review` module (DEC-36 b) - chosen
- Pros: one hash, one staleness rule, one segregation check for audit, tax, close and statements; Home counts agree because they read one projection; the schema lands whole before real data.
- Cons: a large red schema in S3 and S4; service lines wait on the slots; fieldwork migrates once (ADR-134).

### Option B: generalise `review_decisions` (DEC-36 a)
- Pros: reuses a proven insert-only, human-only table.
- Cons: `review_decisions` is a judgement on evidence, not an approval of reviewable content at a level; levels, hashes, notes and cards would be bolted on.
- Why rejected: DEC-36 chose (b), and the glossary keeps `review_decision` distinct from `sign_off`.

### Option C: per-service-line tables
- Pros: each line moves alone.
- Cons: several staleness and segregation rules on the most sensitive records; Home needs a union of every table.
- Why rejected: the opposite of ADR-134's single-engine reasoning.

## Consequences
**Positive**
- Review records are insert-only, attributed, timestamped and bound to a content hash; staleness can never be edited away.
- A new service line becomes reviewable by registering, not by adding tables.

**Negative / costs accepted**
- Four red migrations before the C3 schema freeze; the review module joins mutation testing with a recorded floor.
- Owners must keep `content_hash` current in every write path.

**Follow-up work created**
- **Schema:** `NNNN_review_core` and `NNNN_review_cards_checkpoints_issues` (P-04-T03, T04); decision-table tests (P-04-T13).
- **Contracts:** `docs/contracts/review-grammar.md` and three C3 stub PRs (P-04-T07, T08, T11).
- **Matrix and rules:** condition types `not_preparer_of_target` and `reserved_role`, the six static rules, generated I-AGENT-NEVER (P-04-T15).
- **Fieldwork:** migrate `item_signoffs`, `review_notes`, `workpaper_signatures` onto `review` (ADR-134, P-04-T18 and T21).

## Enforcement
- [ ] Lint rule: `SIGNOFF-001`, `DECISION-001`, `PROPOSAL-001`, `CHECKPOINT-001`, `ISSUE-001`, `FIELD-001` in `abacus_tools/quality/banned_patterns.py`.
- [ ] Architecture / dependency rule in CI: import-linter keeps `review` free of `agents`; `schema_check` keeps sign-off, review-note, decision and checkpoint tables owned by `review`.
- [ ] Test: generated I-AGENT-NEVER for every resolution action; UPDATE or DELETE on each insert-only table raises `insufficient_privilege`; an insert whose `actor_kind` differs from `app.actor_kind` is refused; the R-SO property suite; `fvv_policy_dormant` refuses `policy`.
- [ ] Reviewer agent checklist item: no stored stale flag; no new sign-off table outside `review`; no model-computed option or diff.

## Guidance for agents
Register the target, then call the review API. Compute hashes and options in code. Never write a status that can be computed.

**Do**
```
review.register_reviewable("workpaper", provider)          # owner supplies content_hash
await review.api.record_sign_off(ctx, target, level, seen_hash=h, statement_version=v)
```

**Don't**
```
UPDATE sign_offs SET stale = true WHERE ...                 # staleness is computed
op.create_table("return_signoffs", ...)                     # a second sign-off model
```

## Revisit when
A service line needs a review act the grammar cannot express, or P-08 (policy principal) is accepted and its migration drops `fvv_policy_dormant`.

## Related
- P-ID: P-07 (DEC-36), drafted by P-04-T01. Plan alias "ADR-133" maps to ADR-160 (`docs/adr/backlog.md`).
- Extends: ADR-004 (immutable, versioned records), ADR-005 (humans decide). Builds on ADR-134 (fieldwork rides this grammar), ADR-131, ADR-132, ADR-136 (work items and gate facts), ADR-145 (`visible()` on the `work_item` scope), ADR-147 (functions and `eqr_reviewer`). Companion: ADR-161 (suggestions, proposals, approval grants and Undo).
- Docs: `docs/plan/03-backend-architecture.md` sections 3.7 and 4.7; `docs/plan/epics/P-04.md`; `docs/product/glossary.md` (Sign-off, Decision card, Checkpoint, Approvals).
