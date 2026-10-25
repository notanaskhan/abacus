---
id: TASK-5005
title: "Additive gateway output-check registry; the AgentBlocks check registered by agents"
spec: SPEC-318
acceptance_criteria: [AC-11]
risk_zone: red
status: done
branch: task-5005-output-checks
worktree: agentwt
created: 2026-10-26
updated: 2026-10-26
---

## Plan keys
P-09-T04 (partial: the registry and settle rule; `converse()` arrives with P-10).

## Plan
- **`ai_gateway/output_checks.py`:**
  - `register_output_check(kind, check)`: one check per kind; re-registering the same function is a no-op;
  - `run_output_check`: an unknown kind fails closed with `no_check`;
  - `settle(kind, output, repairs_used)`: passed, or one repair, then unsupported. A failure carries a code and a path, never the text.
- **Agents:** `blocks.check_blocks` over a `BlocksTurn` (payload, facts, citations), registered as `agent_blocks` when the module imports.
- **`call()` and `_call()` are untouched;** a test reads their source to guard that. No workflow or replay history changes.
- **Rollback:** revert the PR.

## Notes
- **Mistake to avoid:** during TASK-461's rebase I used `git checkout --ours/--theirs` on generated client files. `protected-paths.md` lists that as denied. Regenerate instead.

## Progress log
- test_output_checks (7) and test_blocks (20) pass. lint-imports keeps all 5 contracts.

## Definition of done
- [x] Targeted tests pass.
- [x] check-fast passes.
