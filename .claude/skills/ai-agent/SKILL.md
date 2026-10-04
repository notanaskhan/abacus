---
name: ai-agent
description: How to add or change an AI agent or model step — spec, prompt, context builder, tools, handoff, evaluations. Use for any work involving model calls.
---

# AI agent pattern

**Reference:** `docs/architecture/reference/ai-agent.md` (from the walking skeleton's screening step).

## Order of work
1. **Spec** in `backend/src/agents/specs/<id>.yaml` — shape, prompt@version, tier, escalation tier, schemas, tools, limits, autonomy, work class, confidence routing, untrusted inputs, evaluation suite (ADR-047, 069).
2. **Prompt** in the registry, versioned (ADR-019).
3. **Context builder** — five layers in order: instructions, firm, engagement, examples, task input; per-layer budgets (ADR-051).
4. **Output schema** extending `Handoff`: action, confidence, rationale, structured citations, unverified items (ADR-054, 066).
5. **Tools**, if a loop: narrow, typed, authorised (ADR-049, 025).
6. **Evaluation suite** — normal, failure-taxonomy, adversarial and regression cases; thresholds on the dangerous error (ADR-081).

## Rules
- Workflow shape unless the path truly can't be fixed (ADR-046).
- Code computes; the model judges (ADR-050).
- Never import provider SDKs or agent frameworks outside `ai_gateway` (ADR-019, 057).
- Agents propose; never decide (ADR-005).
- Tests use the fake model; evaluations use the pinned real model (ADR-076).
