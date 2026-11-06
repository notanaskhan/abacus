---
id: TASK-3008
title: A-04-T22 mode gap — prompt, mapping and the drafter's document channel
spec: SPEC-620
acceptance_criteria: [AC-1, AC-23]
risk_zone: red
status: done
epic: A-04
plan_key: A-04-T22
branch: s25-a04-t22 (stacked on s25-a04-t43)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"On the fake model the Keystone cell carries two verified citations (BH-EBP-110 step 4 and SOC 1
p.14), the draft records 2 waiting inputs, and the gap cases pass."

## Plan (red)
- `agents/section_sources.py`: `ModePage`, `ModeDocument`, `ModeInputs`, `register_mode_mapping`.
- `agents/section_draft.py` (PROTECTED): context documents and waiting inputs; `D<n>` citations as
  `document_text` claims; run output `waiting_inputs`.
- Prompt `workpapers.section_draft.gap@v1`; spec v4 (gap prompt, `request_item.read`); codegen.
- `assurance/draft_mappings.py` gap mapping; registered in `assurance/api.py`.
- Suite: Keystone gap case (thresholds unchanged).
- Rollback: revert (the spec returns to v3; gap uses the base prompt).

## Acceptance
| Check | Test |
|---|---|
| Gap prompt registered; mapping registered | `tests/unit/agents/test_a04t22_gap_mode.py` |
| Document citation is a document_text claim | same |
| 2 waiting inputs from open requests | same |
| Gap cases pass on the fake model | `python -m abacus_tools.evals --agent workpapers.section_drafter --route fake --mode gap` |

## Progress log
- 2026-11-02: built. Security review of the red diff at the S25 end review.

## Decisions made during this task
DEC-2058.
