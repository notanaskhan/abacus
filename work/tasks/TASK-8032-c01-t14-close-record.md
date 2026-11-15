---
id: TASK-8032
title: "C-01-T14: close kind provider and record service — generate, status machine, list, summary"
spec: SPEC-655
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13]
risk_zone: amber
status: in-review
branch: c01-t14-close-record
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T14
---

## Objective
The close record behind CLS-01 and CLS-02: twelve closes for a Monthly close engagement, the
status machine, assignments, the portfolio with tiles and summary, the record's summary VM,
`visible()` and walls.

## Plan
1. [x] `closes/service.py`: `generate_closes` (AC-13; BD1 and BD7 from practice's calendar),
   `reconciled_facts` (AC-2), `list_closes` (AC-1, AC-3, AC-4), `running_closes`,
   `close_summary` (AC-7), `close_for` (C-01 §4.4), `move_status` (AC-9 to AC-12), `set_assignees`
   (AC-8), `start_close` (the system's Not started → In progress).
2. [x] `closes/repository.py`: close rows, plan versions and accounts, the newest reconciliation,
   schedule and procedure per account, running runs. `closes/kind.py` writes entity, BD1 and due
   date and reports the close's status. `closes/events.py`: `close.status_changed`.
3. [x] Contract routes wired: `GET /v1/closes`, `/closes/running`, `/closes/{id}`, `PUT
   …/assignees`, `POST …/status`, `POST /v1/engagements/{id}/closes:generate`; client
   regenerated.
4. [x] Owner reads added: `review.api.open_issue_counts`, `open_issues_among`;
   `requests.api.binder_document_counts`, `pending_request_counts` (`requests/close_counts.py`);
   `practice.api.business_days_between` (QC-7); `engagements.api.reassign_work_item` (AC-8).
   `banned_patterns` MODULE_DEPENDENCIES: `closes → practice`.
5. [x] Tests: `tests/integration/test_c01t14_close_record.py` (AC-1, 2, 4, 9, 10, 11, 12, 13).
Rollback: revert; no migration.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010).
- `2026-11-15` — Built. A move to In review at 20 of 21 answers 409 `accounts_not_reconciled`
  with `account` = the first missing plan account; a run in progress answers `run_in_progress`;
  Approved, Delivered and Locked run C-02's guard or fail closed; an agent is refused 403 and
  `decision.refused_non_human` is audited in its own unit of work; If-Match is the close's row
  version (409 `stale_version`). Walled and non-team closes are absent because every read
  filters the `close` work items by `visible()` on `close.read` (`work_item_facts`). Past due
  counts business days on practice's calendar (QC-7). Not run (end pass).
- Also fixed: C-01-T11's registry additions used `|=` on uppercase constants (pyright
  `reportConstantRedefinition`); now `.update(...)`.
- **Partial.** `attest` reads False until P-07's attest flag reaches the close row (closes are
  non-attest in the seed, 01 §9.7); the rail's sync line waits on C-01-T17 (`sync: null`); the
  running pill's run line counts the procedures' own rows until C-01-T20 projects runs.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5020 | Reconciled-count rule; lifecycle in `closes.status`; generator writes missing months; one-holder reassignment | no |
