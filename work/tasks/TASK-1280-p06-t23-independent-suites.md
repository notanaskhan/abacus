---
id: TASK-1280
title: ADR-078 independent AC tests for P-06-T14 (follow-ups v2 and the screening return), the accept-withdrawal race and the screening_results migration rules (P-06-T23)
spec: SPEC-319
acceptance_criteria: [AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-28]
risk_zone: red
status: done
epic: P-06
plan_key: P-06-T23
branch: s9b-independent-suites
test_author: ayushkbhatia
test_session: 2026-10-26, branch s9b-independent-suites (clean sessions following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Tests prove accepted evidence is never withdrawable, withdrawn files are hidden from agents and erased only after 30 days and never while held, and INV-1 holds." The implementing rows already carry suites for T18, T19 and T20 (`backfill/test_p06t18_detached_keys.py`, `test_p06t19_withdrawal.py`, `test_p06t19_security_review.py`, `test_p06t20_screening_aggregate.py`: the hide, the 30-day window and the hold); this row adds what was missing: the T14 independent suite (follow-ups v2, now with the screening return of TASK-1252 and DEC-368), the accept racing a withdrawal at the database that TASK-1172 left here, and the migration tests the row names.

## Plan (red zone)
- **Sources read:** SPEC-319 §5 AC-15 to AC-21, AC-28, §12; C5 contract follow-up and screening-return sections; the `agents` and `evidence` matrix rows; `error-codes.yaml`; `human-only-actions.yaml`; DEC-220, DEC-297, DEC-298, DEC-299, DEC-324, DEC-368; TASK-1006, TASK-1172, TASK-1252 task files; migrations 0010, 0144 and 0154 as the database's own statement of its rules. Not read: the follow-up, withdrawal and aggregate service bodies, or the implementers' own tests.
- **Files:** `backend/tests/integration/backfill/test_p06t23_follow_ups_v2_independent.py` (HTTP); `backend/tests/integration/backfill/test_p06t23_withdrawal_race_and_screening_rows.py` (the app role through `uow`, so the session carries the tenant and actor settings every app write does).
- **Production:** none. **Migrations:** none. **Rollback:** revert the commit.

## Results
**Race and screening rows (42 pass):**
- AC-15 / §12: a withdrawal holding its transaction makes a racing accept wait on the key row and then refuses it (`evidence_withdrawn`); an accept holding its transaction refuses the racing withdrawal (`evidence_accepted`) and leaves the key retained; six unordered races each end with exactly one of the two. The tests assert the second write really waited. A retained key can't be cleared by the app; a withdrawal is the session's own person's (another person, an agent and the system are refused); an agent or the system never accepts.
- AC-21, `version` rows (0010 still holds): the agent writes its proposal, `created_by_kind` is the database's (`agent`; the app may not supply it); once per run; about its own run's version; `action`, `confidence` and `rationale` in range and not null; no aggregate column; no person or system may write one; never updated or deleted by any actor.
- AC-21, `request_batch` rows: code (`system`) writes a chain, each superseding the last with `batch_no + 1`; an agent or person never writes one; out-of-chain rows (older head, repeated, skipped, a second first) refused; no run, action, confidence or rationale; a verdict is required and in range; never updated or deleted; the app can't name its author.
- AC-28: a review decision may name a `version` row and never an aggregate.

**Follow-ups v2 (38 pass, 5 strict xfail):** AC-16 (7 + 1 xfail), AC-17 (2), AC-18 (9), AC-19 (3 + 1 xfail), AC-20 (8 + 1 xfail; partner, manager, senior, staff and client_service draft and send, reviewers don't), walls (1 + 1 xfail), another firm (1 + 1 xfail), the DEC-368 screening return (7). The P-4 tick and the agent refused through its task scope are Q-03-T031's (`backfill/test_q03t031_engagement_agent.py`, TASK-1282).

## Escaped defects (open, held by strict xfails)
- `| ED-081 | 2026-10-26 | S9 | red | migration 0122 abacus_human_only_actions() guard (follow_up.sent) | TASK-1006 | P-06-T23 (TASK-1280) | SEV3 | integration | open | a system actor may write follow_up.sent; agent and policy are refused; test_ac19_the_database_refuses_follow_up_sent_from_the_system |` (known as "Open" in DEC-220; a cross-cutting change to the human-only trigger.)
- `| ED-082 | 2026-10-26 | S9 | red | agents/follow_up_drafts.py draft_for | TASK-1006 | P-06-T23 (TASK-1280) | SEV4 | integration | open | an empty selection never calls authorise, so the route guard answers 500 authz.unchecked_route; expected 201 with no drafts, 404 or 403 |` Held: `test_ac16_a_published_binder_with_nothing_open_drafts_nothing`, `test_inv3_a_walled_member_drafting_over_the_binder_gets_404`, `test_dec43_another_firm_drafting_over_the_binder_gets_404`, `test_ac20_a_client_user_may_not_draft`. The fix needs requests to say which binders the caller may read (cross-module), as ED-058 did for the portal picker. Nothing leaks.

## Spec drift (the tests follow the later decision)
| AC | The spec says | The current contract says | Superseded by |
|---|---|---|---|
| C5 §12 (screening return) | the shared comment is written in one unit of work with the send | decisions and status move with the send; the comment and email follow at delivery | DEC-368 |
| AC-18 | the person's added text is checked at send | checked at edit and at send; either refusal is accepted | DEC-220 |
| AC-16 | "one per client contact" | recipients are the client assignee, else the binder's recipients, else the client admins; template drafts are `drafted_by_kind = agent` | DEC-220 |
| AC-15 | "the other answers 409" | at the database the loser is a check violation (`evidence_withdrawn` / `evidence_accepted`); a withdrawn version answers 404 over HTTP (as if it never arrived) | DEC-298 |

## Spec gaps
- Who may Undo another person's send: 403 or 409 accepted.
- `evidence_withdrawals` takes `erase_after` from the app; the database checks only `erase_after > withdrawn_at`, not the 30 days. The window is the service's (covered over HTTP by `test_p06t19_withdrawal.py`); recorded here, not a defect.

## Progress log
- 2026-10-26: both files written; 80 pass, 5 strict xfail. ED-081 and ED-082 recorded open; no production change.
