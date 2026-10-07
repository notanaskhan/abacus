---
name: ai-agent
description: How to add or change an AI agent or model step — spec, prompt, context builder, tools, handoff, evaluations. Use for any work involving model calls.
---

# AI agent pattern

**Reference:** `docs/architecture/reference/ai-agent.md` (worked example: the evidence screener).

## Order of work
1. **Spec** in `backend/src/abacus/modules/agents/specs/<id>.yaml` — shape, prompt@version, tier, escalation tier, input and output schemas, task scope, tools, limits (tokens, cost, steps, seconds), autonomy `propose`, confidence routing, untrusted inputs, evaluation suite (ADR-047). Regenerate `_specs.py` with `python -m abacus_tools.codegen.agent_specs`; the task scope may only hold actions the matrix gives agents as `task_scope`.
2. **Prompt** in the registry: `ai_gateway/prompts/<id>/<version>.txt`, referenced as `id@vN` (ADR-019). It is the system message: the context builder refuses an instructions layer, and PROMPT-001 rejects inline prompts.
3. **Context builder** — layers firm, engagement, examples and task input, each with a budget (ADR-051). Task data is structured, client strings go in `untrusted=` blocks, and a long list is shortened with `trim=` (it is never cut mid-text). Lists over 200 rows are refused.
4. **Output schema** extending `Handoff`: action, confidence, rationale, structured citations, unverified items (ADR-054, 066).
5. **Tools**, if a loop: narrow, typed, authorised (ADR-049, 025).
6. **Evaluation suite** — normal, failure-taxonomy, adversarial and regression cases; thresholds on the dangerous error (ADR-081).

## Rules
- Workflow shape unless the path truly can't be fixed (ADR-046).
- Code computes; the model judges (ADR-050).
- Never import provider SDKs or agent frameworks outside `ai_gateway` (ADR-019, 057).
- Agents propose; never decide (ADR-005).
- Every call has a per-run budget (earlier usage counts), a per-call timeout (`max_seconds`), one repair, then escalation; usage rows and `ai.call` spans are automatic.
- Code has the last word: verify citations against the source (`citations.verify`) and force `needs_revision` when checks fail.
- Tests use the fake model (`install_fake_responses`); evaluations run with `make evals` (`evals/<suite>/`), with the pinned real model once one is configured (ADR-076).
