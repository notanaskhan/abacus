---
id: TASK-6819
title: "T-04-T31: issues.fix_runner for tax returns and Explain… (ghost-value proposals, In progress, resolution as the approver, verified citations only)"
spec: SPEC-649
acceptance_criteria: [AC-4]
risk_zone: red
status: in-review
branch: s36-t04-t31
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-12
plan_key: T-04-T31
---

## Objective
Setting "Add 1,550 to line 2a and IT-201 line 20" yields one proposal with two cited rows and
status In progress; approval through SHL-10 resolves the issue as a person; Explain returns only
verified citations.

## Plan (red)
- Migration 0812 (on 0811): `issue_runs`, `issue_fix_proposals`, `issue_explanations`, insert-only,
  forced RLS, actor-bound. Registered in `review/registry.py` and `schema_check.py`.
- Review (P-04 slots): fix runner keyed by record type with the person's `AuthContext`; explainer
  slot; `set_fix_instructions` → In progress + `issue_runs`; `explain()` behind the existing
  `POST /v1/issues/{id}/explanations`; `issue_runs.py` (fix proposal link, explanation record,
  `proposal.decided` → resolve as the approver with `issue.resolve`).
- Tax: `fix_runner.py` (`FixRunWorkflow`, activity `tax.fix_runner.fix`), `explain.py`
  (`IssueExplainWorkflow`, activity `tax.explain.explain`), registered in `tax/api.py`.
- Specs v2 `issues.fix_runner`, `tax.return_analyst` (explain); prompts
  `issues.fix_runner.tax@v1`, `tax.return_analyst.explain@v1`; `_specs_v2.py` regenerated.
- Audit: `issue.fix_proposed` catalogued.
- DEC-3413; `docs/contracts/review-grammar.md` note.
- Tests: `tests/unit/tax/test_t04t31_fix_and_explain.py`,
  `tests/integration/test_t04t31_issue_runs_migration.py`.
- Rollback: revert the commit and downgrade 0812 (the tables hold only run links).

## Partial / flagged
- The issue detail's read side (`suggestion`, `fix_instructions`, `fix_run`, `explanations` on
  `IssueDetailOut`) is still empty in `review/contract.py`; it lands with T-04-T29's live swap.
- Pre-existing, not this row: the `return_field_changes` proposal adapter
  (`worksheet_review.apply_field_proposal`) is registered but nothing calls
  `agents.proposal_slots.apply_proposal`, so an approved proposal's values are not written by
  any subscriber found. Check at the end pass review.
- Workflow histories for `FixRunWorkflow` and `IssueExplainWorkflow` are recorded at the end pass.
- The suite cases for `issues.fix_runner` and `tax.return_analyst.explain` in
  `evals/tax_return/suite.yaml`, and their real runs, are T-04-T43's.

## Progress log
- `2026-11-11` — Built (S36). Import smoke-checked; tests written, not run (end pass).
- `2026-11-12` — The founders approved `resolve_on_approval` as a `member_context` caller (DEC-3418).
