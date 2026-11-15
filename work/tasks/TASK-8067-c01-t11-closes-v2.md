---
id: TASK-8067
title: "C-01-T11: migration closes_v2 and requests_cas — reconciliations, schedules, flux, recordings, questions"
spec: SPEC-655
acceptance_criteria: [AC-9, AC-22]
risk_zone: amber
status: in-review
branch: c01-t11-closes-v2
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T11
---

## Objective
Migration `closes_v2` and `requests_cas` (C-01 §4.2 T11): the tables the reconciliation engine
(T22), schedules (T21), flux (T25), recordings and transaction questions (T24) write.

## Plan
1. [x] Migration **0885** on 0884, expand-only, 14 tables through `tenant_table()` with named
   insert grants: `reconciliations`, `statement_lines`, `reconciling_items`,
   `reconciling_item_resolutions`, `reconciliation_matches`, `arrangements`,
   `arrangement_versions`, `close_schedule_results`, `analytic_sets`, `analytic_lines`,
   `analytic_explanations`, `close_entry_recordings` (closes) and `transaction_questions`,
   `transaction_question_events` (requests).
2. [x] Insert-only for every computed or versioned table (ADR-004). Set-later columns granted
   column by column and guarded: `closes_set_once` (an item's issue and entry, an explanation's
   acceptance, a recording's confirmation), `analytic_line_forward` (flux status toward
   acceptance; a discarded draft may fall back to unexplained), `transaction_question_final`
   (answered or withdrawn once).
3. [x] Human-only columns as CHECKs: `reconciling_item_resolutions.actor_kind = 'human'`,
   `analytic_explanations.accepted_actor_kind = 'human'`; an agent explanation must carry its
   P-35 suggestion. Question events: a person asks and withdraws, a client contact answers, the
   system reminds.
4. [x] Registries: `closes/registry.py` (12 tables), `requests/registry.py` (2 tables);
   `tests/security/test_tenant_isolation.py` regenerated.
Rollback: downgrade drops the triggers, the 14 tables and the three functions; no data before
T21–T25.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010).
- `2026-11-15` — Built: migration **0885** (on 0884). Tally CHECKs make `tie` mean difference 0 and
  `off` a non-zero difference; `pending` (no statement yet) leaves the bank side null. Bank-side
  items are deposits in transit, outstanding checks or bank errors; book-side items the
  unrecorded ones or book errors. A statement line is a withdrawal or a deposit, never both.
  Not run (end pass: up/down/up, schema_check, single head).
- **Partial.** `analytic_sets.threshold_policy_version_id` references K-02's
  `threshold_policy_versions`; `transaction_questions.template_id` is a key into R-01's template
  rows (DB content), not a foreign key, because the template store is versioned by key.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5053 | Set-later columns on insert-only tables are column grants plus set-once or forward-only triggers, never open UPDATE | no |
