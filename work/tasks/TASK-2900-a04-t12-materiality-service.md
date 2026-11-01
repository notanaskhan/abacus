---
id: TASK-2900
title: A-04-T12 materiality service (AUD-07)
spec: SPEC-620
acceptance_criteria: [AC-15, AC-16, AC-17, AC-18]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T12
branch: s24-a04-t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

A-04 §3.3: serve AUD-07's materiality record, the code-computed preview, the proposal that raises the `planning_materiality` card, the partner's decision applied as the next version in the same unit of work, and the final-basis reassessment card (No change or Revise).

## Acceptance (backlog)

Only Margaret can decide the Northwind card, deciding writes v2 at 252,200 / 189,150 / 12,610 with materiality.decided in one unit of work, and Oct 6 records v3 No change with the 700 difference.

## Plan

- **Review (C3) slot, additive.** `DecisionKind.apply`: the owner's applier runs inside `decide_card`'s unit of work with an `AppliedDecision` (card, decision, engagement, work item, option, figures); a raise refuses the decision. `review.api.awaiting_cards(tenant, work_item, kinds)` for the owner's record. Matrix: `decision_card.raise` adds manager and senior (an owner's route raises; the agent stays task-scoped).
- **Service `assurance/materiality.py`.**
  - Policy: K-02 `materiality_ranges` in effect today; the row for the audit's segment (EBP dc/db, FS); benchmark key from the label ("net_assets").
  - Benchmark: C9 `trial_balance_view` lines named as the policy names the benchmark (else the mapped FS line), absolute net, Unadjusted or Final.
  - Record: versions (current = newest, earlier Superseded), benchmarks re-run through the engine with prior years from the roll-forward chain's decided versions, the caption from code facts, the pending card, allowed actions.
  - Preview: engine thresholds on the record's benchmark amount; 409 `outside_policy` with `facts.field`.
  - Propose: options (low and midpoint, plus an optional typed `rate_pct`), the card raised with those options (the provider answers only the service's computed card, fail closed), v-next "Proposed" naming the card; 409 `proposal_pending`.
  - Decide applier: v-next "Decided" from the option's figures; `materiality_version.decided` audit, `materiality.decided` outbox; 409 `materiality_record_moved` if a later version exists.
  - Reassess: Final layer at the decided rate (engine `reassess`), the `materiality_reassessment` card with `no_change` and `revise`; applier writes "Reassessed" (thresholds stand) or "Revised" (final-basis thresholds, impact list from `register_materiality_dependents` providers, `materiality.revised` to preparers).
- **Notifications.** `materiality_revised` kind (`materiality.revised`, listed recipients).
- **Contract.** `MaterialityProposalIn.rate_pct` (additive); the four materiality routes live (501 gone).
- **Tests.** `tests/integration/backfill/test_a04t12_materiality_service.py` (AC3.1, 3.3, 3.4/3.5, 3.6 layer gate, 3.9), `tests/unit/assurance/test_a04t12_materiality_keys.py`.
- **Rollback.** Flag `assurance.materiality` off hides every route; no migration.

## Decisions

DEC-1950 (see decision log).

## Progress log

- 2026-11-01: built in abacus-s24 (S24 lane A-04). Tests written, not run (build first, test last). Regenerate (matrix, OpenAPI client, error codes) at the end review.
