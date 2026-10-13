---
id: TASK-067
title: "Cell references in spreadsheet excerpts, for the matcher and the upload reviewer"
spec: SPEC-033
acceptance_criteria: [AC-3, AC-7]
risk_zone: amber
status: done
branch: task-067-cell-references
worktree:
created: 2026-10-13
updated: 2026-10-13
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
TASK-065's follow-up: the matcher's two misses were right answers hidden because a spreadsheet quote named a cell code couldn't find. The model saw rows as "a | b | c" without references, so it had to count columns and rows.

## Plan
- [x] Plan approved by human (founder, 2026-10-13: "proceed with your recommendations", the first follow-up in TASK-065's handoff). Approved by founder: `backend/src/abacus/modules/agents/**`, `backend/src/abacus/ai_gateway/**`, `backend/tests/unit/**`

### Design
1. **Spreadsheet excerpts show each non-empty cell with its reference**, row by row from row 1 ("A1: Payroll register | B3: Gross pay"), in both agents' context builders (`document_citations.sheet_lines`). Verification is unchanged: it reads the same rows by the same reference.
2. **New prompt versions** say so and ask for the reference as shown, quoting that cell's own text: `evidence.upload_review@v3` (reviewer spec v3) and `evidence.inbox_match@v2` (matcher spec v2).
3. **Rerun both suites** on the real model (synthetic tenant, small tier at temperature 0); reports to `docs/operations/`.

## Progress log
- `2026-10-13` — Plan from TASK-065's handoff, approved with it.
- `2026-10-13` — Built: `sheet_lines` in both context builders; prompts `evidence.upload_review@v3` and `evidence.inbox_match@v2` (specs v3 and v2). Reruns on the real model (Haiku 4.5, temperature 0, synthetic tenant): the matcher **passed**, with top-1 rising from 0.95 to 1.0 and the matcher alone from 0.88 to 1.0 ($0.11, 42 attempts); the upload reviewer **passed** every threshold, with quote accuracy 0.97 ($0.05, 28 attempts). Reports: `docs/operations/matching/direct-2026-10-13-prompt-v2-passed.json`, `docs/operations/upload-review/direct-2026-10-13-prompt-v3-passed.json`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
Done. Next: TASK-066 (design awaiting approval).
