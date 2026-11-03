---
id: TASK-3011
title: A-04-T24 mode risk — register drafts as suggestions, Identify wording over code facts
spec: SPEC-620
acceptance_criteria: [AC-21]
risk_zone: red
status: in-review
epic: A-04
plan_key: A-04-T24
branch: s25-a04-t24 (stacked on s25-a04-t23)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"R8's drafted rationale and EBP-03 response arrive as pending suggestions with three verified
citations, and Identify states 10 of 10 and R8 only from code facts."

## Plan (red)
- Slots: `ModeTarget`, `ModeInputs.cells/targets/facts`; drafter lands a mode cell on its target.
- `assurance/draft_mappings.risk_inputs`, `risks.linked_ids`; `workpapers.api.paper_of_kind`.
- Prompt `workpapers.section_draft.risk@v1`; spec v6; route `/risks/{risk_id}/drafts` served.
- Rollback: revert.

## Acceptance
| Check | Test |
|---|---|
| Own prompt and mapping | `tests/unit/agents/test_a04t24_risk_mode.py` |
| Cells land on the risk's fields | same |
| Coverage facts by code | same |

## Progress log
- 2026-11-02: built. The response column waits for A-04-T25's linkage target (DEC-2060).

## Decisions made during this task
DEC-2060.
