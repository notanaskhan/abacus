# review

Zone: red. Pre-registered by F-03-T08 (ADR-140); empty until its first epic.

Will own (docs/plan/03-backend-architecture.md §2.2): Sign-offs, review notes, issues, decision cards and decisions, checkpoints, field value versions, the human-gates projection. Registration slots: reviewables, decision kinds, gate kinds, field owners.

## Content hash and staleness (P-04-T14; DEC-215)
- `review.api.content_hash(value)`: SHA-256 hex of the RFC 8785 canonical JSON (`hashing.py`, no dependency). Amounts are strings; a `Decimal`, NaN, an infinity or an integer past 2**53 - 1 is refused (`NotCanonical`). Owners hash through it (workpapers today).
- `ReviewableFacts` per target through `register_reviewable_facts` / `reviewable_facts` (fail closed).
- `stale_of(tenant, target_type, {target_id: current_hash})`: the newest sign-off per target and level whose hash differs, in one query. No sign-off row is ever updated.

## Human gates (C13; P-04-T16, DEC-320)

`gates.py` is the projector Home reads: `register_gate_source(GateSource(...))` names an owner's gate kind, subject type, read action, the C13 events that may change it and `open_for(tenant, engagement_id | None)`. The projector (`SUBSCRIPTIONS`) reconciles an engagement's rows with what the owner says waits now, idempotent on the event and the subject; `rebuild_human_gates(tenant)` does every engagement. `GET /v1/human-gates` lists open gates assigned to the caller or to nobody, through `visible()`. The agent's four typed proposals register in `agents/gates.py`. `register_gate_kind` is the computed gate check slot (G1 to G5), not this one.

## The sign-off service (P-04-T18, T19; DEC-400 to DEC-402)

`sign_offs.py` serves `GET /v1/sign-offs`, `/eligibility` and `POST /v1/sign-offs` (behind `review.grammar_api`): a live person signs the hash they saw at a level the matrix allows them, and every R-SO rule answers its fixed code (`docs/contracts/review-grammar.md` §2, §6). Rows record initials, engagement role, version, statement version, the adopted agent run (R-SO-8) and when independence was checked; audit and outbox `sign_off.recorded`. `stale.py` is the `StaleSignOffDetector`: on `trial_balance.version_created` and `workpaper.content_changed` it emits `sign_off.went_stale` once per sign-off and hash (notification `sign_off_stale`). SIGNOFF-001 names the only files that reach `record_sign_off` and `sign_target`.

## Review notes, bulk sign-off and decision cards (P-04-T21 to T23; DEC-500 to DEC-504)

`notes.py` serves `/v1/review-notes` and the SPEC-313 routes through one service: bodies sealed (`sealing.py`, migration 0210), reads recorded as `review_content.read` access events, audit subject `reviewable_note` (ED-150), `review_note_raised` to the assignee. `bulk.py` serves `POST /v1/sign-offs:bulk`: each item through `sign_target`, `Idempotency-Key` through `kernel.uow.idempotency`, `bulk_request_id` on the rows, fresh MFA. `decisions.py` serves `/v1/decision-cards` and `raise_decision_card`: options from the kind's provider (`DecisionKind`), numbered history (`decision_card_versions`, 0211), human-only decide with MFA per kind, reassess to No change or a superseding card. DECISION-001 names the only files that reach `decide_card`.
