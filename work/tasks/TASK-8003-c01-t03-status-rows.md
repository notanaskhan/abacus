---
id: TASK-8003
title: "C-01-T03: close status registry rows and copy registries (DF-23)"
spec: SPEC-655
acceptance_criteria: []
risk_zone: amber
status: in-review
branch: c01-t03-status-rows
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T03
---

## Objective
close status registry rows and copy registries (DF-23).

## Plan
1. [x] `docs/product/status-vocabulary.yaml` / status registry: `close` six states (not_started, in_progress, in_review, approved, delivered, locked) plus the on-hold side flag; `close_plan_version` draft · published · discarded; `close_procedure` queued · running · needs_attention · done · failed; `reconciliation` tally pending · tie · off; `analytic_line` statuses; `transaction_question` open · answered · withdrawn.
2. [x] Regenerate StrEnums, OpenAPI enums and `status.ts`.
3. [x] Copy registries for the close screens (UI strings verbatim from the handoff).
Rollback: revert; no consumer reads the rows before T14.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).
- `2026-11-14` — Built. `status-vocabulary.yaml` gains `close_flag` (on_hold side flag), `close_procedure` (the five states under their code name), `close_incorporation`, `close_tally` (pending, tie, off n, Ties once posted, Recorded in QuickBooks, Reconciled), `analytic_line`, `close_plan_version`, `transaction_question` (with client labels) and `ledger_sync` (derived words). The six canonical close states and derived past due were already `close` (blueprint 3.3.1). `_statuses.py` and `status.gen.ts` regenerated.
- **Partial.** The per-screen copy modules (`screens/CLS-*/copy.ts`) land with the close shell (T12) and each screen's own row; T03 puts every status word in the registry so no screen hard-codes one.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5003 | Close status words; "Recorded in QuickBooks", never "posted" | no |
