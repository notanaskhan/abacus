---
id: TASK-5004
title: "AgentBlocks v1: server schema and validators, client renderers, specimen, L4 lint"
spec: SPEC-318
acceptance_criteria: [AC-11]
risk_zone: red
status: done
branch: task-5004-agent-blocks
worktree: agentwt
created: 2026-10-26
updated: 2026-10-26
---

## Plan keys
P-09-T03 (AgentBlocks server schema), P-09-T06 (renderers and specimens) (partial).

## Plan
- **Backend, `agents/blocks.py`:**
  - the Pydantic discriminated union of nine parts, with every field classified;
  - `Fact` (the run's fact registry entry);
  - `validate_blocks(payload, facts, citations)`, which runs the shape check, then the copy lint, then reference checks;
  - `BlocksRejected(code, where)`, which never carries the offending text.
- **`RunItemOut.blocks`:** an optional, server-validated payload, exposed in OpenAPI so the client gets the types.
- **UI, `packages/ui/src/agent/blocks.tsx`:**
  - `AgentBlocks`, `AgentProse` and `factText`;
  - the `p-09-agent-blocks` specimen on the seed's Northwind figures.
- **Web:**
  - the dock renders `blocks` when an item carries them;
  - ESLint L4 covers `model_text` outside AgentText, AgentProse and AgentBlocks.
- **Rollback:** revert the PR. There are no migrations, and no live path changes: nothing produces blocks yet.

## Notes
- ADR P-24 (DEC-41) is still owed: the decision log names ayushkbhatia to draft it. This schema follows P-09 §3.7 and should be checked against the ADR when it lands.
- The output-check registry (P-09-T04) is not built. No model call produces blocks until P-10's `converse()`.
- L4 is narrowed to `model_text`. `blocks` and `segments` already name other things in ClientGuidance and ADM-02.

## Progress log
- test_blocks passes 20 tests, including properties: no free number and no markup ever validates.
- blocks.test passes 4 tests; gallery 32; AgentDock 4.

## Definition of done
- [x] Targeted backend tests pass, including classification, status vocabulary and OpenAPI.
- [x] check-fast passes.
