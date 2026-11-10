---
id: TASK-6723
title: "T-04-T25: tax.return_drafter v1 (mode draft): spec v2 workflow, ReturnDrafterWorkflow, box-to-field mapper, judgment, citations, self-check, Initial draft checkpoint"
spec: SPEC-649
acceptance_criteria: [AC-9.3, AC-11.1]
risk_zone: red
status: in-review
branch: s35-t04-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: T-04-T25
---

## Objective
On the fake model the Feld draft proposes the IT-201, W-2, Sch E p2 and IT-653 worksheets with cited fields and raises the box 18A issue, nothing changes until Kevin approves the checkpoint, and a missing consent leaves the run waiting_on_inputs.

## Plan (red: written before the build)
- `tax/drafter.py` (new, PROTECTED): the code rules. These are `BOX_MAP` (P-11 box keys to worksheet fields, per year with inheritance), `map_boxes`, `worksheet_set` (IT-201 always; W-2; Sch E p2 for a 1065/1120-S K-1; IT-653 for a NY PTET attachment), the box 18A self-check (tax-exempt interest: IT-201 line 20 needs the obligations' state), engine fields never proposed, `ReturnDraftJudgment` (the model judges only TSJ and new-this-year notes), the `judged_set` guard (an unoffered key, a TSJ outside T/S/J or a digit in a note falls back to code's default) and `draft_hash`.
- `tax/drafter_run.py` (new): one run as the agent. Steps:
  - `tax.read_return` first; `consent_required` there is a wait on `consent_7216`, with no model call.
  - `tax.list_documents`, then the extracted boxes.
  - `tax.read_worksheet` per offered worksheet.
  - The judgment (`tax.return_drafter@v1`; a refused gateway call leaves code's defaults).
  - Box citations verified as the agent (`box_claim` on each field's `field` anchor); an unverified box becomes a gap.
  - The self-check issues (`review.api.create_issue`, idempotent by `source_ref`).
  - One proposal through `tax.propose_field_changes`, and the Proposed checkpoint "Initial draft" naming it.
- `tax/drafter_workflow.py` (new): `ReturnDrafterWorkflow` (running, then draft; waiting_on_inputs until `inputs_ready` or `stop`; then succeeded or failed), the activity `tax.drafter.draft`, and `start_draft` (TAX-04 "Draft with Agent"). Registered in `tax/api.py` WORKFLOWS/ACTIVITIES.
- `agents/run_start.py` (new): `open_capability_run` writes the v2 run row for a person (`agent_run.start`, `require_live_human`, the run number from the firm's counter, the spec's task scope, one audit event). `agents.api` exports it, plus `spec_v2` and `load_run_v2_context`.
- `agents/specs/v2/tax.return_drafter.yaml` with the generated `_specs_v2.py` (codegen run); prompt `tax.return_drafter@v1`; `tax/agent_tools.py`, so the registry gate and codegen see T-04-T19's tools.
- `review/checkpoints.propose` gains `name` (a fixed code label); `evidence.extracted_read.ReadField` gains `page_no` and `bbox` for box citations.
- History recorder `abacus_tools/workflows/record_return_drafter.py` and the replay test.
- Tests:
  - `tests/unit/tax/test_t04t25_drafter_rules.py`: the Feld set and mapping, box 18A, engine and low-confidence rules, the judgment guard and the hash.
  - `tests/integration/test_t04t25_return_drafter.py`: start and draft on Feld without consent waits on `consent_7216`, with no model call and no proposal; a non-person is refused.
  - `tests/workflows/test_t04t25_return_drafter_replay.py`.
- Rollback: revert. Nothing starts the drafter until TAX-04's control calls `start_draft`, and `tax_agents.enabled` stays off for real firms.

## Partials (flagged)
- **The Feld draft acceptance itself:** proposal, cited fields, box 18A issue and the checkpoint on approval. It needs the Feld boxes and their page words seeded (P-11's word layer, so `document_text` verifies). The rules are unit-held here; the end-to-end case belongs to T-04-T35 (labelled cases) and P-10-T49 (journey).
- **Worksheet creation:** the set is code's and the model's judgment, but a worksheet the return does not have yet (IT-653) is not created. The drafter proposes field values on existing worksheets only. Creating a worksheet with `origin = agent` on checkpoint approval needs a worksheet-creation proposal adapter (T-04-T16's service has none).
- **Judgment storage:** the judged TSJ and new-this-year notes are returned in the run's outcome but not written to the worksheets (that needs the same adapter).
- **Not built:** `inputs_ready` has no sender yet (the consent capture should signal it), and the TAX-04 route that calls `start_draft` is not here.
- Replay histories are recorded at the S35 end pass (Docker).

## Progress log
- 2026-11-10: built; imports and codegen ran; tests run at the end pass.
