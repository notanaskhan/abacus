---
id: TASK-7602
title: W-02-T04 status registry and glossary rows (filters, season stages, ApprovalCard words)
plan_key: W-02-T04
spec: SPEC-653
acceptance_criteria: [AC-L2, AC-R2, AC-W1, AC-W2]
risk_zone: red
status: in-review
branch: w02-t04-status-rows
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
C2 rows for W-02: WB-01's filter labels, the Gather · Prepare · Review · Deliver season stages as
context labels over return statuses (Q7), the ApprovalCard's "Waiting on you" and "✓ Approved by"
words; glossary rows suggested prompt, context item, session drill, run artifact preview and season
stage.

## Plan
- `docs/product/status-vocabulary.yaml` (protected): object `workbench_session_filter` (five
  derived codes); `season_stage` context labels on every `return` code; `approval_card_owner`,
  `approval_card_other` on `proposal.pending`; `approval_card` on `proposal.approved`.
- Regenerated `kernel/_statuses.py` and `packages/ui/src/status.gen.ts`.
- `abacus_tools/codegen/status_vocabulary.py`: a proper-noun set (`Agent`) for the sentence-case
  rule, so "Via Agent" (WB-01 c, verbatim) validates. No other rule changes.
- `docs/product/glossary.md`: five rows under "New terms: workbench".
- Test `packages/ui/src/status.w02t04.test.ts`.
- Rollback: revert; the rows are read by nothing until W-02-T14.

## Deviations (DEC-4602)
- `rejected` and `fixing` map to Deliver (inferred; the epic's matrix has neither in the seed).
- Filed + Accepted carry a fifth context label, Done, so AC-A6's Open 79 / Done 145 is one lookup.

## Progress log
- `2026-11-12` — Rows added and regenerated (DEC-4602). Tests run at the S40 end pass.
