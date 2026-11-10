---
id: TASK-6602
title: "P-05-T05: Comments v2 service and routes: anchor slot, threads, post, correct, redact, mentions with team expansion, resolve, reopen, mute, read, batch counts, share guard"
spec: SPEC-650
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-16, AC-39]
risk_zone: amber
status: in-review
branch: s34-p05-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: P-05-T05
---

## Objective
A comment on a registered anchor is sealed, mentions only engagement members, resolves and
reopens as events, and a share on an internal anchor is refused.

## Plan (amber)
1. `collaboration/anchors.py` (new): `register_anchor(kind, provider)`, `AnchorFacts`, the
   provider protocol, locator normalisation; the two live SPEC-032 kinds can never register.
2. `models.py`, `repository.py` (new): the eight 0760 tables mapped; every list with `visible()`.
3. `errors.py`, `events.py` (new): the contract's fixed codes; `comment.created`,
   `mention.created` (one per person), `comment_thread.resolved/reopened`, the to-do events.
4. `candidates.py` (new): mention and assignee candidates by `could(…, comment.read|todo.read)`:
   walled people absent, non-members greyed for a search, never the agent.
5. `threads.py` (new): open, post, correct, redact (fresh MFA by the matrix), resolve, reopen,
   mute, read, share guard, threads on an anchor, batch counts with unread.
6. `routes.py` (new; routes moved out of `contract.py`, which keeps the shapes): the thread routes
   live; conversion stays 501 (P-05-T09); to-do routes stay 501 (P-05-T06). Idempotency stores
   identifiers only, never a body.
7. `notifications/catalogue.py`: `mention.created` → kind `mention` (subject `comment_thread`),
   recipients re-checked against the team at fan-out (AC-8), its sentence.
8. `audit_trail/activity_reviewed.py`: the new thread actions reviewed onto the fallback (AUD-29
   shows only deletions and redactions, OQ-4); `collaboration/audit_targets.py` owners.
9. Tests: `tests/unit/collaboration/test_p05t05_threads.py`; the HTTP AC suite is P-05-T07's.
Rollback: `collaboration.v2` stays off; revert the PR (no migration).

## Progress log
- `2026-11-10` — Built dark on ADR-236 as proposed (DEC-3200). ruff and pyright clean on the
  module; tests not run (end pass). Partial: no anchor kind is registered by this row (`todo`
  arrives with P-05-T06, `workpaper` with P-05-T09), so every thread route answers 409 until then;
  "Convert to review note…" stays 501 (P-05-T09); `make generate` pending (errors tuples changed).
  The T07 test files got lint-only fixes here.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3202 | Thread target, unread rule, mention re-check, share coverage | no |
