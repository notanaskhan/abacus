# Reference: AI agent

Spec, prompt registry, context builder, gateway, handoff, citation verification and metering (SPEC-000 §22), from the walking skeleton (TASK-011, 011b). Binding rules: ADR-005, ADR-019, ADR-025, ADR-047, ADR-050, ADR-052, ADR-054, ADR-057, ADR-066, ADR-070.

## The spec

```yaml
# modules/agents/specs/evidence.screener.yaml (compiled into specs/_specs.py)
id: evidence.screener
prompt: evidence.screen@v0
tier: small
task_scope: [evidence.read, screening.run]
limits: {max_output_tokens: 800, max_cost_usd: "0.03", max_steps: 1, max_seconds: 60}
autonomy: propose
untrusted_inputs: [account_names]
```

- The YAML is the source. `python -m abacus_tools.codegen.agent_specs` renders `_specs.py`; `--check` (and a test) fails on drift. Never edit `_specs.py`.
- `AgentSpec` (`extra="forbid"`) is validated at import, so an agent without a valid spec can't run. It must name a registered prompt, a `single_call` agent has `max_steps: 1`, and `autonomy` is `propose`.
- The task scope may hold only actions the matrix gives agents as `task_scope` (`agent_may_hold`). An `agent: deny` action such as `evidence.accept` can't be listed.
- The runtime reads prompt, tier, limits, scope and untrusted inputs from the spec, not from constants.

## Prompts

- Files: `ai_gateway/prompts/<id>/<version>.txt`, referenced as `evidence.screen@v0`. A used prompt is never edited: a change is a new version.
- `registry()` loads them with their SHA-256; `prompt(ref)` raises `UnknownPrompt`.
- PROMPT-001: outside `ai_gateway`, no inline prompts, no `ModelRequest`, no instructions layer from a literal.

## Context

```python
context = (ContextBuilder()
    .text("engagement", f"Requested period {period}.")
    .task({"totals": {...}, "cells": {...}, "account_names": names},
          untrusted=screener.untrusted_inputs, trim="account_names")
    .build())
```

- Five layers in fixed order (instructions, firm, engagement, examples, task), each with a token budget. Over-budget text is cut and flagged (`context.truncated`). The instructions layer is refused: instructions are the registered prompt (ADR-057).
- Untrusted fields become JSON `<untrusted name="...">` blocks with `<` escaped, so a value can't close the block or pose as instructions (ADR-052).
- The task layer is never cut mid-text. `trim=` names one list to shorten from the end; otherwise `ContextTooLarge`. Any list over `MAX_ROWS` (200) raises `DatasetTooLarge`.
- **Code computes, models judge (ADR-050):** the context carries totals, counts, cell positions and account names, all computed by `citations.facts`. Never rows of amounts.

## The gateway call

```python
result = await call(GatewayCall(
    purpose=screener.purpose, prompt=screener.prompt, tier=screener.tier,
    output_schema=ScreeningOutput, budget_usd=screener.limits.max_cost_usd,
    attribution=Attribution(agent.tenant, agent.engagement_id, run.agent_id, run.id),
    context=context, max_output_tokens=screener.limits.max_output_tokens,
    timeout_seconds=screener.limits.max_seconds))
```

- A call missing a purpose, a Pydantic output schema, a positive budget, a known tier, an attribution or a registered prompt raises `GatewayRefused`.
- Output is validated against the schema. Invalid output gets one repair (the same request plus where it failed, never the model's text), then `status="escalated"` with `output=None`.
- **Budget:** checked before every attempt on estimated cost. For an agent run the budget is the run's: earlier usage for the run counts. A refusal on the first attempt raises `BudgetExceeded`.
- **Timeouts:** each provider call is bounded by `timeout_seconds`. A timeout or provider failure raises `ProviderError` (retryable) and bills the input tokens, so retries can't spend past the budget as free calls.
- **Metering:** every attempt writes a `usage_records` row (firm, engagement, agent, run, prompt version, model, tier, tokens, cost, outcome, inputs hash) and a `model.called` audit event, in its own unit of work. Never call `call` inside one. Inputs are logged by hash only.
- **Trace:** one `ai.call` span (prompt reference, tier, agent, status, attempts, cost, model) with an `ai.attempt` event per attempt. Never prompts, context or output (see observability.md).
- **Providers:** `ModelProvider` is the seam (PROVIDER-001: endpoints and SDKs only in `ai_gateway`). `FakeModel` is local and test only; `agents.fake_responses.install` scripts the screener's answers, and tests replace the responder to exercise invalid output, repair and fabricated citations.

## Handoff and citations

```python
class ScreeningOutput(Handoff):          # confidence, rationale, citations, unverified
    action: Literal["ready_for_review", "needs_revision"]
```

- Every agent output extends `Handoff` and declares `action` as the literal actions it may propose (ADR-054). A citation is a cell, plus an optional exact quote or value.
- `citations.verify` checks each citation against the stored spreadsheet: the cell exists, a quote equals its text, a value equals its number. Failures carry `cell_not_found`, `quote_mismatch` or `value_mismatch` and are shown as unverified, never as fact (ADR-066).
- `citations.facts` is strict about the rendered layout (constants shared from `evidence.api`): exactly one Total row with no code, every row above it a coded line, no amounts after it. Otherwise `SheetLayoutError`, so a client line can't pose as the Total row.

## The service

```python
agent = await load_agent_context(tenant_id, run_id)    # proven from the running run row
outcome = await screen(agent)
```

- `create_screening_run`: one run per agent and event (unique on source event), for `requested_by` from `evidence_version.created`. No initiator, an inactive initiator or no ledger snapshot means no run.
- **Authority (ADR-025):** `AgentContext` is issued only inside identity, from the run row and the initiator's live membership. The task scope is the run's intersected with the current spec's; a run from another spec version is failed. `authorise` grants an agent an action only if the matrix says `task_scope`, the action is in its scope, and the initiator is allowed the same action. For agent-only actions (none held by a human role, such as `screening.run`) the initiator must be allowed `AGENT_ONLY_REACH` (`evidence.read`). `visible()` applies the same intersection.
- `screen` takes a per-run advisory lock (`AgentRunBusy` on overlap), authorises `evidence.read`, reads verified content, computes facts, calls the gateway and verifies citations. It then records the `screening_results` proposal and completes the run in one unit of work, authorising `screening.run` on the locked engagement.
- **Code has the last word:** `needs_revision` is forced when any citation fails, debits and credits differ, or the Total row disagrees with the lines. Confidence below the spec's `confidence_routing.below` takes its route. A trimmed context is noted in `unverified`.
- **Failures:** `TERMINAL` errors (`SheetLayoutError`, `DatasetTooLarge`, `ContextTooLarge`, `BudgetExceeded`, `GatewayRefused`, `Forbidden`, `NotFound`) fail the run with a code (`agent_run.failed`) and re-raise. `ProviderError` leaves it running for the workflow's retry. Output still invalid after repair escalates the run (`agent_run.escalated`) with no result.
- **Agents propose:** screening never changes a request item's status, and no agent can accept, reject, waive or confirm (AGENT-001).
- **Results route:** `GET /v1/engagements/{id}/screening-results` (`evidence.read`) returns the latest result per version through `visible()` and records `screening_result.read`. Model text (`rationale`, `quote`, `unverified`) is rendered in the SPA only through `AgentText` (ADR-065).

## Starting it

- `SUBSCRIPTIONS` maps `evidence_version.created` to `start_screening`, which starts workflow `screening:<tenant_id>:<evidence_version_id>`. A redelivery attaches to it or finds it finished.
- `ScreeningWorkflow`: `screening.create_run` (none: `skipped`), then `screening.screen` (heartbeats, 4 attempts), and on any failure or cancellation `screening.fail_run`, retried until it succeeds. Changes use `workflow.patched` and new replay histories (ADR-090).

## Evals

- `evals/screening/` runs the real pipeline (retrieval, then the agent through the gateway) on synthetic data, with `FakeModel` today. Invariants on every case: the result is an agent proposal, citations are verified, client text stays in `<untrusted>`, spend stays in budget. Cost per case goes to `backend/.evals/screening.json`; `make evals` runs them.
- A new agent ships with its spec, prompt, handoff model, eval suite and fake responder.

## Not yet
- A real provider (it arrives with the spec that enables real calls) and escalation to `escalation_tier`: an escalated run goes to a person today.
- Multi-step agents and tools (`shape` is `single_call`).
- Uploads don't pass `requested_by`, so only retrievals are screened.
