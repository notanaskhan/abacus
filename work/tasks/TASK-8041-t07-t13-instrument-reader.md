---
id: TASK-8041
title: "T-07-T13: capability tax.instrument_reader v1 and InstrumentReaderWorkflow"
spec: SPEC-656
acceptance_criteria: [AC-1.4, AC-1.5, AC-2.1, AC-2.2, AC-2.3, AC-2.4]
risk_zone: red
status: in-review
branch: t07-t13-instrument-reader
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: T-07-T13
---

## Objective
The reader capability: spec v2 (workflow, medium tier, `tri`, untrusted `instrument_text`,
autonomy propose, $0.60), its prompt, the code that settles the model's answer, the workflow and
the route that starts it, with C19's consent refusal before any model call.

## Plan (red: written before the build)
1. `agents/specs/v2/tax.instrument_reader.yaml`; `_specs_v2.py` and `_eval_suites.py`
   regenerated.
2. `ai_gateway/prompts/tax.instrument_reader/v1.txt`; `evals/tax_instrument_reader/suite.yaml`.
3. `tax/instrument_reader.py`: schemas, `settle`, `read_instrument`, `InstrumentReaderWorkflow`,
   `read_activity`, `start_read`; registered in `tax/api.py`; `POST …/instrument/read` wired.
4. `tax/agent_tools.py` imports the T-07-T14 tools so the spec validator sees them; the tools'
   read rows carry `id` (ADR-049).
5. **Protected** `feature-flags/tax.yaml`: `prompt.tax.instrument_reader` (DEC-4713).
Rollback: revert; no run starts while `tax.fiduciary_workpapers` is off.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029); plan above written before building.
- `2026-11-15` — Built (DEC-5027). The spec validator (`agent_specs_v2`) passes. Not run
  otherwise (end pass: unit, the replay test, the eval suite on the fake model, security review).
- **Partial.** The workflow's recorded replay history is written at the end pass from a real run
  on the dev stack; the eval runner wiring (`abacus_tools.evals`) and the CPA labels are T-07-T17;
  the firm's AI-policy stage is firm data.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5027 | Workflow shape, consent first, code settles, propose only | no |
