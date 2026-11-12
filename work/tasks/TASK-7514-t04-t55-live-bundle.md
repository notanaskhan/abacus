---
id: TASK-7514
title: T-04-T55 post-window live-path bundle (draft-run entry, return-frame tabs, export hook)
plan_key: T-04-T55
spec: SPEC-649  # T-04 AC-13.2
acceptance_criteria: [AC-13.2]  # merges after the window; live tax-pilot tests green with the flags off
risk_zone: red
status: in-review
branch: t04-t55-live-bundle
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The live-path edits AC-13.2 holds for the first train after Apr 20: the export field-profile hook in
`tax/export.py`, the draft-run entry route for TAX-02, and the shared return-frame tab registration.

## Plan
- **Draft-run entry.** `tax/draft_entry.py` (new): `run_draft` — a person only (agent, system and
  support 403, client 404), the return found among the viewer's work items (404 otherwise),
  `tax_return.draft_run` authorised on the engagement with the return as the work item, 409
  `draft_not_allowed` from final approval on, then T-04-T25's `start_draft`.
  `workspace_contract.draft_run_route` (was 501) calls it behind `tax_agents.enabled` and
  `tax.review_workspace`. `overview.ACTIONS` adds the action so `allowed_actions` tells TAX-02 when to
  show Run draft (the button's wiring is T-04-T46).
- **Return-frame tabs.** `tax/return_tabs.py` (new): `register_return_tab(tab, flag, order, forms)`
  and `frame_tabs`; `overview.record` lists T-02's tabs then the registered ones whose flag is on.
  `tax/api.py` registers Review, Issues and Activity behind `tax.review_workspace` for 1040 and
  1040-X; T-05 registers its entity tabs on the same seam.
- **Export field-profile hook.** Already on `main`: T-04-T30 (TASK-6805) wired
  `export_fields.export_values` into `export.export_return`, checking each worksheet key against
  `integrations.api.engine_field_profile()` (409 `engine_field_unmapped`). Asserted here.
- `docs/architecture/error-codes.yaml` regenerated (`draft_not_allowed`).
- Test `tests/unit/tax/test_t04t55_live_bundle.py`.
- Rollback: revert; with `tax_agents.enabled` and `tax.review_workspace` off the frame shows only
  T-02's tabs and the route is 404, exactly as before.

## Partial
- The staging soak and both founders' approval, and the Apr 27 production promotion, need staging.

## Progress log
- `2026-11-12` — Built (DEC-4514). Tests run at the S39 end pass.
