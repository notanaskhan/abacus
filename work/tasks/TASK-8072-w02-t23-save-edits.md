---
id: TASK-8072
title: "W-02-T23 rest: Edit... on Save to Files is honoured, and the save question offers attach_only"
spec: SPEC-653
acceptance_criteria: [AC-W4, AC-W5]
risk_zone: red
status: in-review
branch: w02-t23-save-edits
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: W-02-T23
---

## Objective
Finish W-02-T23's two buildable partials (DEC-5012). The third, firm-level folders, needs a
firm folder store that no row has built (W-02 §11 R5).

## Plan (red: agents, the prompt and the spec)
- **P-04:** `proposals.register_edit_validator(kind, fn)`. `approve_proposal` calls a kind's
  validator on the person's edits before anything is written. It answers 422 `proposal_invalid`.
- **`file_save` (AC-W4):**
  - `file_tools._validate_save_edit` accepts only "‹Deliverables, Workpapers or Correspondence›
    › ‹name›". The name must be 1 to 200 characters with no path. The approver must be able to
    save to the engagement (`file.save`, as `files.propose_save` checks, AC-Q2).
  - `save_approved` reads the newest approving decision's edit and files under its folder and
    name. Without an edit it keeps `set_ref`'s folder and the artifact's name.
- **Prompt (AC-W5):**
  - `workbench.assistant@v2` adds one bullet. When the person has not said where a file goes, ask
    one question: the engagement folders they can write, and "Attach it to this session only"
    (`attach_only`).
  - The spec moves to version 2 on `@v2`. `@v1` is unchanged (immutable once referenced).
  - `_specs_v2.py` and `_eval_suites.py` are regenerated.
- Rollback: revert. The spec goes back to v1; v2's text stays unreferenced.

## Partial
- Firm-level folders: these need a firm folder store (R5).
- The real-model eval run of `@v2` needs the evaluation account (human, as W-02-T25). The
  fake-model suite runs at the end pass.

## Progress log
- `2026-11-15` — Built (DEC-5058). Lint and pyright are clean; tests run at the end pass.
