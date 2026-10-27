---
id: TASK-1474
title: Independent AC tests for the AUD-06 read model, ties and reviewable, plus the AUD-06 authz review (A-02-T21)
spec: SPEC-333
acceptance_criteria: [AC-5, AC-9, AC-10, AC-11, AC-12, AC-13, AC-17, AC-28]
risk_zone: amber
status: done
epic: A-02
plan_key: A-02-T21
branch: s12-ledger
created: 2026-10-27
updated: 2026-10-27
test_author: ayushkbhatia
test_session: 2026-10-27, s12-ledger (ADR-078 separate test session; did not write A-02-T10 or A-02-T17)
---

## Objective
"The suite covers walls, independence, agent refusal and tie goldens, and the authz review note
is merged before Tue Jun 1, 2027."

## Plan
Tests only, from SPEC-333 AC-5, AC-9 to AC-13, AC-17, AC-28, the A-02 epic §3.2 and §3.3, C9 v1
§2 and §6, the assurance and workpapers matrix rows and `error-codes.yaml`.

- `backend/tests/integration/backfill/test_a02t21_aud06_ties_independent.py` (shares
  `tb_support.py` with TASK-1473): walls 404 identical to a missing engagement on every TB route,
  another firm 404, off-team and client users refused, `independence_pending`, the agent refused
  every C9 action and `sign_off.prepare`, the human-only and cited CHECKs on check versions,
  server figures, `allowed_actions` per role, `newer_snapshots`, the tie goldens (rollforward
  312,400.00; BrokerWindow off 1,560.00 with its line flag), results computed on read,
  `citation_required`, a citation of another engagement, define and edit audited with a stale
  version refused, the issue link (`Idempotency-Key` required, replayed, reuse refused, set once,
  another engagement's issue 404, stale 409, extra fields and reviewers refused), and "Changed
  after sign-off" with no sign-off row updated.
- The authz review note of the AUD-06 routes (below).

Rollback: delete the file.

## Progress log
- 2026-10-27: suite written (build first).

## Results (per AC)
- AC-9 walls (every TB route 404 identical to a missing engagement, no hidden count), another
  firm 404, off-team and client users refused, independence (per DEC-270): pass.
- INV-1: the agent refused every C9 action, `ledger.pull`, `connection.reconnect_request` and
  `sign_off.prepare`; check versions refuse an agent row and an uncited expected value: pass.
- AC-5, AC-17: server decimal strings, `allowed_actions` per role, `newer_snapshots`: pass.
- AC-10, AC-11 goldens: rollforward 288,500.00 + 96,200.00 - 57,450.00 - 14,850.00 = 312,400.00
  tie; BrokerWindow off 1,560.00 with its `does_not_tie` flag; results computed on read: pass.
- AC-12: `citation_required` (422), another engagement's citation refused: pass.
- AC-11, AC-28 issue link: key required, replay, set once, other engagement 404, stale 409,
  extra fields 422, reviewer 403: pass. AC-13: "Changed after sign-off" with no sign-off row
  updated: pass.

## Strict xfails (ED rows in docs/quality/escaped-defects.md)
- ED-175 `test_ac10_a_balanced_check_ties_when_debits_equal_credits`: defining a balanced check
  answers 500 (CHECK "a balanced check has no expected value").
- ED-176 `test_ac12_defining_and_editing_are_audited_as_the_person`: an edit is audited
  `tie_out_check.changed`, not C9 §7's `tie_out_check.updated`.
- ED-177 `test_ac28_an_idempotency_key_reused_for_another_issue_is_refused`: a reused key with
  another issue answers 409 `tie_out_check_issue_linked`, not 422 `idempotency_key_reused`.

## Spec drift (DEC-551)
`independence_pending` on reads only with `g2_blocks_view` on an attest client (DEC-270
supersedes AC-9's wording); C9 §6 statuses vs error-codes.yaml; a tie check's `citation_ids` are
evidence citations of the engagement (SPEC-310), not C4 citation rows.

## Authz review of the AUD-06 routes (A-02-T21, before M9)
Reviewed 2026-10-27 against `assurance.yaml` and `workpapers.yaml`, by test at the HTTP boundary.
Every route under `/v1/engagements/{id}/trial-balances` resolves the engagement in the tenant
first: a wall and another firm answer 404 with a body identical to a missing engagement (list,
view, candidates, leadsheets, layer view, leadsheet by area, checks, export, issue link). Reads
need `trial_balance.read` (team roles; client and agent refused); adopt, annotate and define
deny the reviewer and the agent; export is partner, manager and senior with a fresh second
factor and denies staff, reviewer and the agent; the issue link needs `Idempotency-Key`.
Findings: none on access control. Open items: ED-176 (audit name) and ED-177 (key reuse code)
are correctness, not exposure; DEC-551 (C9 §6 statuses and the independence wording) needs a
contract edit by the C9 owner. Not covered here: `not_offshore` on the export (no offshore
fixture in this suite) and the SPEC-313 sign-off levels beyond L1.

## Progress log
- 2026-10-27: targeted pass, foreground, -n 2: 28 passed, 3 xfailed (the agent refusal set re-run after adding two actions: 7 passed).
