---
id: TASK-8304
title: "C-01-T29: Capability close.agent v1 (red)"
spec: docs/plan/epics/C-01.md §5
acceptance_criteria: [C-01-T29]
risk_zone: red
status: in-review
branch: c01-t29-close-agent
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: C-01-T29
---

## Objective
Capability close.agent v1 (red).

## Plan (red)
1. `agents/specs/v2/close.agent.yaml` (workflow; tools read/compute/propose from C-01-T28; task scope close.read, suggestion.create, issue.create, decision_card.raise; untrusted uploads and client answers; no TRI; suite evals/close_agent) and `_specs_v2.py` regenerated.
2. Four registered prompts `close.agent.{run,intake,bank_rec,aje}@v1`; `codegen/eval_suites.py` binds the three other modes to the frozen suite (`_eval_suites.py` regenerated).
3. `closes/agent.py`: input/output schemas, `settle` (AgentBlocks validation: number provenance, known facts and verified citations, no markup, no claimed human act; closed options), `answer` (one gateway call per mode), `scoped_tool` (`out_of_scope`), the run mode's binding to `closes.close_run`, fake-model scenario responses.
4. `agents/api.py` exports `validate_blocks` and `BlocksRejected`.
5. Tests: `tests/unit/closes/test_c01t29_close_agent.py`. Rollback: revert; no flag turns the capability on (firm opt-in and the AI-policy stage are G-02's).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5304). The spec loads (spec_v2 checks the tools' actions against the task scope); the unit file ran green (9 tests). Gates and
  tests run once at the S47 end pass (build first, test last).
