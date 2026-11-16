---
id: TASK-8303
title: "C-01-T28: Close tools on C17 in closes/agent_tools.py"
spec: docs/plan/epics/C-01.md §5
acceptance_criteria: [C-01-T28]
risk_zone: amber
status: in-review
branch: c01-t28-close-tools
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: C-01-T28
---

## Objective
Close tools on C17 in closes/agent_tools.py.

## Plan (amber)
1. `closes/agent_tools.py`: `close.read_checklist`, `close.reconcile` (compute, the T22 engine over statement lines, the month's register and the prior period's open items), `close.read_upload_table` (compute: numeric column totals, no cell text), `close.read_register`, `close.propose_aje` (propose: a suggestion on `reconciling_item.aje_draft`; amount and bank side by code; never an entry), `close.plan_history_profile` (compute).
2. Six tool description prompts `ai_gateway/prompts/tool.close.*/v1.txt`.
3. Registered in `agents/tools/catalogue.py`; `reconciling_item` suggestion target with its engagement lookup (`closes/issues.py`).
4. Tests: `tests/unit/closes/test_c01t28_close_tools.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5303). The C17 registry check passes at import (it first refused the propose tool for naming records without `tool_targets`; fixed). The unit file ran green (3 tests). Gates and
  tests run once at the S47 end pass (build first, test last).
