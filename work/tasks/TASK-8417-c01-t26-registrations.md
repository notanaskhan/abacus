---
id: TASK-8417
title: "C-01-T26: Closes registrations"
spec: SPEC-655
acceptance_criteria: [AC-17, AC-48]
risk_zone: amber
status: in-review
branch: c01-t26-registrations
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T26
---

## Objective
Spec section: docs/plan/epics/C-01.md §4.6, §4.8. Registrations: C13 gate kinds (plan publish requested, flux acceptance pending, reconciliation L1 due); the HOME-01 closes count; C15 search for a close; C16 notification kinds (run finished with exceptions, run needs input, plan publish requested, client answered, requests published) with read-time text; the KNW-04 closes examples provider; the portal home source closes.py.

## Plan (amber)
1. `closes/registrations.py`: gate sources `close_flux_acceptance` (proposal; newest set per close and basis with explained lines) and `close_reconciliation_sign_off` (sign_off_request; newest version per account with nothing open and no current L1, assigned to the close preparer) with presenters; `closes` home count (the month before today, CLS-01's four tiles, office narrowing); the `close` C15 projection (CLS-02, triggers close.created/status_changed, list_ids); subscribers on `agent_run.ready_for_review` (open issues > 0: `close_run.finished` to preparer and reviewer), `agent_run.needs_input` (`close_run.needs_input`), `transaction_question.answered` (`close_question.answered` to the issue's assignee); the `aje_thresholds` KNW-04 examples provider.
2. Events: `reconciliation.computed`, `reconciling_item.resolved` (reconciliations), `analytic_set.computed`, `analytic_line.explained`, engagement_id on `analytic_line.accepted` (flux), the preparer on `close_requests.published` (intake), `transaction_question.answered` (requests); C13_EVENTS rows.
3. Notifications catalogue: five kinds with templates (`ledger_sync_paused` already C-01-T17).
4. `portal/home_sources/closes.py`: close work cards (C2 close stages) and the POR-11 answer to-do, behind `closes.portal_requests`.
5. Flux: an accepted line refuses a new explanation (`flux_line_accepted`); the engine is read through `workpapers.api` (BOUND-001); the export function is `workbook_of` (L12).
6. Tests: `tests/unit/closes/test_c01t26_registrations.py`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5412). Lint, pyright and banned patterns clean on touched files; app and worker import. Partial: `close_run_needs_input` fires beside P-10's generic `run_needs_input` (both reach the starter; de-duplication is a C16 change); the HOME-01 caption month comes from the tile's `period=` filter (HomeCount has no caption field); the notification email bodies are DB templates still to import per environment. Gates and tests run once at the S48 end pass (build first, test last).
