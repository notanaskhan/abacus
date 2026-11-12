---
id: TASK-7317
title: "T-04-T37: tax.assistant v1 loop capability: spec v2 loop, prompt tax.assistant@v1, workbench session bound to a tax_return, read and compute tools plus propose_field_changes, availability with consent and boundary reasons, History per return"
spec: SPEC-649
acceptance_criteria: [AC-T37]
risk_zone: red
status: in-review
branch: s37-t04-t37
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T37
---

## Objective
On the fake model the 9:29 AM question returns a cited answer and one proposal for box 18A 1,550
with 2 citations, no reply contains 'I approved' or 'I changed', and an unconsented taxpayer gets
the agents-off state with no model call.

## Plan (red)
- `agents/specs/v2/tax.assistant.yaml` (loop, medium, `plan: required_when_writes`, read
  and compute `tax.*` tools plus `tax.propose_field_changes`, `tri`, untrusted tool results and
  document text) compiled into `_specs_v2.py`; prompt `ai_gateway/prompts/tax.assistant/v1.txt`.
- Inline turns stay read-only (P-10-T43's `ReadOnlyPorts`); a change answers a plan whose one
  child run proposes the field changes (SHL-10 approves; the checkpoint is the review's).
- `tax/assistant_sessions.py` and routes `POST/GET /v1/tax/returns/{id}/assistant-sessions`
  (`session.create`/`session.read`, `tax_return.read` on the return): availability first
  (`agents.api.capability_ready`, P-10-T45's reasons); unavailable answers 409
  `assistant_unavailable` with `facts.reason` and opens nothing.
- Workbench: `open_session(subject=…)`, `sessions_for_subject` (History), and `post_message`
  reads availability before opening a turn's run (no run, no model call; the turn's notice
  carries the reason).
- Eval: `assistant_ridgeline_box18a_proposal` in the tax return suite's cases (1,550, two
  verified citations, the plan's declared write); the suite passes on the fake outputs (151).
- Tests: `tests/unit/agents/test_t04t37_tax_assistant_spec.py`,
  `tests/integration/agent_tests/test_t04t37_tax_assistant.py`.
- Rollback: revert (the spec disappears from the registry; sessions bound to returns read as any
  session).

## Partial
- Real-model runs of `tax.assistant` (T-04-T43) and its Bedrock clearance (`client_data: none`
  until then).
- TAX-08's host wiring to these routes and the session stream (T-04-T34's drawer) lands with
  the T-04-T29 swap.

## Progress log
- `2026-11-12` — Built (S37). App import smoke, ruff clean, the suite passes on the fake outputs;
  tests written, run at the end pass.
