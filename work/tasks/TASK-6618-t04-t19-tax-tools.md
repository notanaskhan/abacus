---
id: TASK-6618
title: "T-04-T19: Tax tools on C17 in modules/tax/tools.py with tool.tax.*@v1 description prompts"
spec: SPEC-649
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: red
status: in-review
branch: s34-t04-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: T-04-T19
---

## Objective
A tri read without both §7216 consents for the taxpayer and tax year fails with
`consent_required` before data is fetched, no tool output holds a full TIN, and every propose
tool creates a proposal, never a value.

## Plan (red)
1. `backend/src/abacus/modules/tax/tools.py`: twelve tools with `@agent_tool` (tax may import
   agents). Reads: `tax.read_return`, `tax.list_documents`, `tax.read_worksheet`,
   `tax.read_pass_through_activity`, `tax.read_prior_year`. Computes: `tax.compare_years`,
   `tax.compute_pass_through_facts`, `tax.compute_residency_facts`,
   `tax.compute_state_allocation` (code in `tax/compute/individual`, ADR-050). Proposes:
   `tax.propose_field_changes`, `tax.propose_pass_through_treatments`, `tax.propose_residency`
   through `agents.api.create_proposal`, answering identifiers only.
2. Every tool takes `client_entity_id` + `tax_year`, the runtime's conventional TRI subject, so
   C19 consent is checked before the handler runs; the runtime scrubs TINs and pins the client
   scope. Propose inputs declare `tool_targets` (engagement + TRI subject).
3. Handlers scope the return to the run's engagement: the engagement's client entity must be the
   named taxpayer (`engagements.api.entity_of`), else `NotFound`.
4. Prompts `ai_gateway/prompts/tool.tax.<name>/v1.txt` (12).
5. `worksheet_review.register`: `return_worksheet` becomes a suggestion target (engagement of the
   worksheet), the target type T-04-T15's `apply_field_proposal` reads.
6. Tests: `backend/tests/unit/tax/test_t04t19_tax_tools.py`.
7. Rollback: drop the import in `tax/api.py`; no migration, no flag.

## Progress log
- 2026-11-10: built. Names read "pass-through" for K-1 (`read_k1_activity`,
  `compute_k1_facts`, `propose_k1_treatments` in the backlog): C17's name grammar
  `^[a-z][a-z_]*\.[a-z][a-z_]*$` holds no digits, as T-04-T15's `pass_through_treatment` target.
- Partial: the consent refusal, TIN masking and scope pinning are the runtime's (P-10-T22) and
  apply because each tool is `data_class="tri"` with the conventional fields; the end-to-end
  refusal test through `runtime.call_tool` against a seeded unconsented taxpayer is T-04-T42's
  (independent AC tests, S38) and is not written here. Tests run at the S34 end pass.

## Decisions
- DEC-3211.
