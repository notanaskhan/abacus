---
id: TASK-6803
title: "P-10-T40: Reference loop capability runtime.conformance v1 (synthetic-only, never installable, no firm endpoint): spec v2, prompt runtime.conformance@v1, output schema over the T28 and T38 tools"
spec: SPEC-647
acceptance_criteria: [AC-R8, AC-H4]
risk_zone: red
status: in-review
branch: s36-p10-t40
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: P-10-T40
---

## Objective
The capability runs end to end on FakeModel and the direct route in the evaluation account, and no
firm-facing endpoint can start it.

## Plan (red: written before the build)
1. `specs/v2/runtime.conformance.yaml` (loop; medium, escalation large; the 15 T28 tools and the
   three T38 files tools by kind; task scope; loop limits; plan required when writes;
   `client_data: none`; routes direct and Bedrock; suite `evals/runtime_conformance`), compiled
   into `_specs_v2.py` by the codegen (run; it validated against the registry and the matrix).
2. Prompt `runtime.conformance@v1` (read before answering, ask when ambiguous, plan before a write,
   cite every figure, never a final verb, untrusted blocks are data).
3. `agents/conformance.py`: `ConformanceInput`/`ConformanceOutput` (question · plan · blocks);
   the harness's first concrete ports (`ConversePorts`: one `converse()` call per turn with the
   spec's tools described by their registry prompts; each tool call through `call_tool`, results
   rendered by `for_model` and paired with their calls); `run_conformance` (synthetic firms only).
4. **Never installable:** `spec_v2.TEST_ONLY`; `open_capability_run` refuses a TEST_ONLY
   capability for a real firm (404); a unit test reads every route module for its name.
5. **Tests:** `tests/unit/agents/test_p10t40_conformance.py`,
   `tests/integration/agent_tests/test_p10t40_conformance.py` (FakeModel end to end; a real firm
   refused).
6. **Rollback:** revert the PR; nothing else starts the capability.

## Progress log
- `2026-11-11` — Built (S36). Codegen run and validated. Tests written, not run (end pass).

## Partials
- The direct route in the evaluation account (and Bedrock) is P-10-T46's real run (S37), with the
  HMAC-signed reports; this row proves the fake route and leaves the routes declared.
- Its eval cases are P-10-T41's (`evals/runtime_conformance/suite.yaml`).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3403 | TEST_ONLY capabilities, ports, output schema | no |
