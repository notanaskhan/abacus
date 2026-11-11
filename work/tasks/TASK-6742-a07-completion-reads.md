---
id: TASK-6742
title: "A-07 completion reads: AUD-18, AUD-19 and AUD-21 on the server's rows"
spec: SPEC-644
acceptance_criteria: [AC-1, AC-2]
risk_zone: amber
status: in-progress
epic: A-07
branch: s35c-completion-reads
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-11
updated: 2026-11-11
plan_key: S35-followups-2
---

## Objective
- **AC-1.** `GET /v1/audits/{wi}/eqr`, `…/completion`, `…/subsequent-events`, `…/legal-letters`,
  `…/going-concern`, `…/representation-letter`, `…/versions` and `…/versions/{n}` answer from the
  rows the A-07 services write, behind the same gate (client 404, the matrix action on the work
  item, `audits.completion`). The writes stay 501.
- **AC-2.** On the archive load at Oct 9, 10:05 the reads give Thomas's concurred review (10 of
  10, notes cleared), the checklist in the firm template's words, and the letter signed and dated
  as of the report date.

## Plan
- `assurance/completion_reads.py`: one read per route over the existing tables; names through
  `identity.api.names_of`; sealed text opened with its writer's fingerprint; `allowed_actions` from
  the matrix on the work item. EQR-only acts are dropped for anyone but the assigned EQR and once
  concurred; concur only when ready.
- Small read helpers in their owners' APIs: `review.api.note_states` (a note's state without its
  body, so a 10 s poll writes no access event), `agents.api.last_completed_run`,
  `eqr_service.checklist_wording`.
- The screens already call the generated client (A-07-T25, T17, T28): no model change, so
  `make generate` changes nothing.
- No invented copy: a procedure's title is its key until the firm's procedure list carries
  wording; the letter's signers stay empty (C7 holds them) (DEC-3307).
- Rollback: revert; the routes go back to 501.

## Progress log
- 2026-11-11: reads written and wired; ruff, pyright and import contracts clean; integration
  assertions added to `test_a07t41_archive_loaded.py`.
