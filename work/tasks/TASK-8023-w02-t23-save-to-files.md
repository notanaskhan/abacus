---
id: TASK-8023
title: "W-02-T23 part 1: Save to Files wiring (attach-only, writable folder, access sentence)"
spec: SPEC-653
acceptance_criteria: [AC-W1, AC-W5, AC-Q2]
risk_zone: red
status: in-review
branch: w02-t23-save-to-files
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: W-02-T23
---

## Objective
Bind the WB-01b save-location answer to `files.propose_save`, compute the ApprovalCard's
folder-access sentence, and keep approve, reject and Undo on P-04's grants (W-02 §3.9).

## Plan (red: written before the build)
- `agents/file_tools.py` (PROTECTED, agents):
  - `ATTACH_ONLY` option key; `attach_only_chosen(run)` reads the run's answered `agent_questions`
    for it; `files.propose_save` refuses (`save_not_requested`) when it was chosen (AC-W5).
  - `files.propose_save` refuses a folder the approver cannot write now (`folder_not_writable`,
    AC-Q2; `member_could(initiator, file.save)`).
  - `access_sentence(folder)`: "The engagement team can open Deliverables." carried in the
    proposal's `set_ref.access` and `ProposeSaveOut.access_sentence` (AC-W1).
- Unchanged and relied on: the grant's `not_before` +10 s and Undo (`proposals.approve_proposal`,
  `issue_grant`), consumption that re-checks the approver's `file.save` (AC-W7),
  `file_approved_copy` attributed "<approver> via Agent" with the grant id (AC-W2).
- Test: `tests/unit/agents/test_w02t23_save_to_files.py`; the database paths run in W-02-T24.
- Rollback: revert the commit (no migration).

## Progress log
- `2026-11-14` — Part 1 built. ruff and pyright clean; tests at the end pass.
- **Partial.**
  - Firm-level folders ("Files › Firm reports › TY2025 season", the office-managers sentence) need a firm folder store no row has built (SPEC-653 N-01 finding, W-02 §11 R5); a firm-level run still answers `engagement_required`, and the option list is engagement folders plus "Attach it to this session only".
  - Edit… (file name and folder as a new proposal version, AC-W4): P-04's `approve_proposal` edits a row's After text only. `save_approved` still files under `set_ref`'s folder and the artifact's name, so an edited folder or name is not yet honoured. It needs a `file_save` edit validator (writable folders only) and the consumer reading the edited value. Proposed for N's review, not guessed.
  - The assistant prompt must offer the `attach_only` key on the save question. The prompt is protected and immutable once referenced, so this is a new prompt version (N).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5012 | the attach-only binding and the engagement-folder access sentence | No |
