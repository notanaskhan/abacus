---
id: TASK-1279
title: C13 consumer contract tests and independent AC tests for the human-gate projector (P-04-T17)
spec: SPEC-313
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-04
plan_key: P-04-T17
branch: s9b-independent-suites
test_author: ayushkbhatia
test_session: 2026-10-26, branch s9b-independent-suites (clean session following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Tests written in ayushkbhatia's session pass in the provider CI and fail if a walled client's gate is counted." P-04 §3 F9 (C13): idempotency on the event, a rebuild yields the same rows, wall exclusion (INV-3), the DF-25 kind taxonomy, Daniel Reyes's 11 = 3 + 6 + 2 in one query. As TASK-1190, no SPEC covers C13; `spec` names the review grammar's nearest spec for the docs gate.

## Plan (red zone)
- **Sources read:** P-04 §3 F9, §4.2 (`human_gates`), §4.3; `docs/contracts/review-grammar.md` ("Human gates (C13 read)", §2 row, "Home"); DEC-320; DF-25; the `review.yaml` matrix row; migrations 0093 and 0152 as the database's statement of its CHECKs; `review.api` signatures only (the slot). Not read: `review/gates.py` bodies, `agents/gates.py` `open_*` bodies, the implementer's `test_p04t16_human_gate_projector.py`.
- **Files:** `backend/tests/contracts/review_grammar/test_c13_human_gates.py` (contract half, no database); `backend/tests/integration/backfill/test_p04t17_human_gates_independent.py` (HTTP read on the migrated testcontainer, projector driven through `review.api.SUBSCRIPTIONS` and `rebuild_human_gates`).
- **How a consumer is simulated:** decisions, sign-off requests and exports have no owner on main (DEC-320), so the suite registers three consumer sources through `register_gate_source` (as I-01 will), with `open_for` reading a per-firm dict. The agent's typed proposals are seeded as the agents write them.
- **Production:** none. **Migrations:** none. **Rollback:** revert the commit.

## Results (all pass: 21 contract, 25 integration)
- **DF-25 taxonomy:** wire enum, table CHECK and the slot agree on the seven kinds; the slot refuses any other kind, a non-snake subject type, an event outside the fixed set, and a second owner of one subject type (`test_c13_*`).
- **Fixed event set:** C13's six events (DEC-320's five plus `fulfilment.voided`, R-01 Story 2.2); the worker hands each to the projector.
- **Read:** the list envelope with `counts` per kind; `human_gate.read` for the contract's nine firm roles only (agent, system and client roles denied).
- **F9 Home:** one query reads Daniel's 3 + 6 + 2 = 11 (`total` 11); someone else's gates never count; an unassigned gate waits on everyone who may read it; kind and engagement filters; keyset pages cover the 11 once.
- **F9 story 1:** a redelivered event leaves every row (including `updated_at` and `source_event_id`) and the audit count unchanged; one row per subject; a projection that writes is audited `human_gate.projected` by the system on the engagement; a no-change rebuild writes nothing; a rebuild from an empty table yields the same open rows and the same read; an old event delivered late converges on the owner's state; a settled subject goes `done` and a returned one reopens the same row; a `voided` row stays voided.
- **F9 story 2 (the row's acceptance):** a walled person's counts and list drop the walled client's gates and no identifier of it appears; after a rebuild too; a colleague not walled still sees them; a person off the engagement, another firm (own and foreign tenant header) and a client principal read none; flag off answers 404.
- **F9 story 3:** a screening, an upload review with a shown flag and a passed guidance draft project as three unassigned `proposal` gates; a rebuild reproduces them; a person's accept of the version, replayed from the product's own outbox, closes the screening and review gates and leaves the draft; replaying the whole history again changes nothing; walls hide a walled client's proposals.

## Defects
None.

## Spec gaps (tests accept either answer)
- A client principal calling `GET /v1/human-gates`: contract §2 lists no client role and the matrix denies them, but the read answers 200 with an empty page rather than 403. Nothing is read or counted; the test accepts 403 or an empty 200.
- A filter on a walled engagement: 404 or an empty page with no count.
- The inbox-match source is not exercised here (it needs an inbox file and a match run); it is the same slot as the other three.

## Progress log
- 2026-10-26: written in one clean session; 46 tests pass. No defect, no production change.
