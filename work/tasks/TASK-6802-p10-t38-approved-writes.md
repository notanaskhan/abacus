---
id: TASK-6802
title: "P-10-T38: Proposals bridge and approved writes: propose tools through the P-04 review and agents APIs, proposal.decided deriving approved, partially_approved, rejected, approved_write executor consuming identity grants after not_before with approver rights re-checked, after_ref = grant id; files.build_workbook (C11), files.propose_save, files.save_approved"
spec: SPEC-647
acceptance_criteria: [AC-P1, AC-P2, AC-P3, AC-P5]
risk_zone: red
status: in-review
branch: s36-p10-t38
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: P-10-T38
---

## Objective
Hannah Leclerc's approval saves the workbook only after 10 s under the actor Hannah Leclerc via
Agent, Undo inside 10 s leaves Files unchanged, and an approver who lost file.save blocks it.

## Plan (red: written before the build)
1. **Migration 0811** (on 0810): `run_artifacts.storage_version_id`, `sha256` (insert grants);
   agents registry INSERT_COLUMNS. Expand-only.
2. **C17 fix (protected):** `scope_action` on `ToolDecl`/`AgentTool`; `validate_tool` requires it
   for `approved_write` (not its own action, no final verb) and refuses it elsewhere; the runtime
   authorises an `approved_write` with it. Contract §3 note (additive).
3. **Tools (`agents/file_tools.py`):** `files.build_workbook` (compute; deterministic xlsx via
   `kernel.safe_xlsx`, stored by `evidence.store_workbook`, artifact id derived from run + bytes),
   `files.propose_save` (propose; `file_save` proposal through `create_proposal`, citations from
   the artifact; `writes_waiting` + 1), `files.save_approved` (approved_write; files the copy
   through `evidence.file_approved_copy` as agent on behalf of the approver; `file.saved`
   after_ref = grant id; artifact `saved`; counters).
4. **Bridge (`agents/approved_writes.py`):** held-effect slot; `approve_proposal` issues the grant
   (`not_before` + 10 s) and names it on the decision; `proposal_undo` voids it for held kinds and
   emits `proposal.undone`; subscriber on `proposal.decided`/`proposal.undone` re-derives the run
   outcome and starts `ApprovedWriteWorkflow` (own module, `approved_write:<tenant>:<grant>`);
   the activity spends the grant through `call_tool` from `load_write_context`; refusals become
   `proposal.write_failed {reason}`; a void `write_undone`.
5. **Identity:** `consumed_grant` (grant id and approver for the effect) and `grant_status`.
6. **Tests:** `tests/unit/agents/test_p10t38_approved_writes.py`;
   `tests/integration/test_p10t38_approved_writes.py` (AC-P1 timing and attribution, AC-P2 Undo,
   AC-P3 approver lost the action, AC-P6 no grant).
7. **Rollback:** revert the PR (0811's downgrade drops the columns); no grant is issued for any
   kind but `file_save`.

## Progress log
- `2026-11-11` — Built (S36, build first). Tests written, not run (end pass). Workflow history for
  `ApprovedWriteWorkflow` to record at the end pass.

## Partials
- Firm-level runs (#4118 "Files › Firm reports › TY2025 season") can't propose or save: proposals
  need an engagement and there is no firm Files store yet (W-02). Engagement runs work end to end.
- `files.build_workbook` writes xlsx with `kernel.safe_xlsx`; C11 renders PDF and DOCX only, so
  "via C11" is read as its determinism rule (ADR-042), not its renderer.
- The folder is one of the engagement's Files folders (Deliverables, Workpapers, Correspondence);
  `files.list_folders` and the folder access sentence (WB-03d) are W-02's.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3402 | Held effects, C17 `scope_action`, executor, outcome, scope | no (additive to C17 v1) |
