---
id: TASK-025
title: Model routes, with a second route configured
spec: SPEC-010
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9]
risk_zone: red
status: awaiting-plan-approval
branch: task-025-model-routes
worktree:
created: 2026-10-07
updated: 2026-10-07
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-010 (approved, Q1–Q5): `direct` and `bedrock` route adapters, per-agent route lists, failover by admission over routes, route attribution in usage and evaluation records, route enablement by parity, and the Titan embedding adapter.

## Scope
All of SPEC-010. Excluded: live credentials and staging configuration (TASK-014), cross-family failover, and batch-API execution.

## Context to load
- Spec: `docs/specs/SPEC-010-model-routes.md`
- ADRs: ADR-073, ADR-019, ADR-072, ADR-070
- Code: `ai_gateway/` (`__init__`, `admission`, `providers`, `embeddings`), `abacus_tools/evals`, `modules/agents/spec.py` and `service.py`

## Plan
- [ ] Plan approved by human

### Design (for founder review)
1. **The `ai_gateway/routes/` package:**
   - `Route = Literal["fake", "direct", "bedrock"]`;
   - `route_provider(route)` returns the `ModelProvider` for that route (`FakeModel` for `fake`, built lazily from settings for the others);
   - `direct.py`: `AnthropicDirect` (`AsyncAnthropic`);
   - `bedrock.py`: `AnthropicBedrock` (`AsyncAnthropicBedrock`) and `BedrockTitanEmbedder` (boto3 `bedrock-runtime` in a worker thread, one text per request, since Titan v2 takes one input).
   - Both Anthropic adapters:
     - send the system prompt as a cached block (`cache_control`);
     - map usage tokens, counting cache reads and writes as input;
     - normalise errors: 429 is `rate_limited` with `retry-after`; 5xx, 529, timeouts and connection errors are an outage; 401 and 403 are `auth`.
   - Dependency: `anthropic[bedrock]` (allowlisted). The ruff ban on `anthropic` is narrowed from `ai_gateway/**` to `ai_gateway/routes/**`.
2. **Settings** (`kernel/config.py`):
   - `model_routes` (default `("fake",)`);
   - `model_catalog`: tier → `{name, ids: {route: model_id}, usd_in, usd_out}`, with defaults equal to today's fake models and prices;
   - `anthropic_api_key` (secret, optional) and `bedrock_region`;
   - `route_parity`: route → `{checked_on, report_sha256}`;
   - `outage_block_seconds` (30);
   - `embedding_provider` (`fake` or `bedrock-titan`).

   `MODELS`, `cost()` and the rest read the catalog. `provider_limits` is keyed by `route:model_id`.
3. **Admission over routes:**
   - `admit`, `block` and `release` take the route, which fills `provider_capacity.provider`; it replaces today's `settings().model_provider`.
   - `_admitted` walks tiers × usable routes. Usable means:
     - listed in the call's `routes`;
     - in `model_routes`;
     - the route has a model ID for the tier;
     - parity is within 90 days (`fake` exempt);
     - not excluded for this call (auth failure);
     - eligible.
   - In synthetic environments the only route is `fake`, and the spec's routes are validated but not used (D1).
4. **Failover in `_call`:**
   - on a 429, block that route's model for `retry-after` (as today);
   - on an outage, block it for `outage_block_seconds`;
   - on 401 or 403, exclude the route for this call and log `provider.auth_failed` (an alert).

   The second attempt is re-admitted, so it lands on the next usable route. Attempts stay at 2.
   - `GatewayResult.route`, span `ai.route`, and `usage_records.route` for every outcome, embeddings included.
5. **Eligibility per route** (D3):
   - `eligible(tenant, agent, route, tier, model, prompt)` applies to every route in non-synthetic environments, not just the cheaper tiers (ADR-073 enforcement).
   - Evaluation mode pins the route as well as the tier (`evaluation_tier(tier, route)`) and isn't gated.
   - The evaluation runner takes `--route`, and `eval_runs.route` is recorded.
6. **Agent specs:**
   - `routes: tuple[Route, ...]` is required, non-empty, distinct, and excludes `fake`;
   - the screener spec gets `[bedrock, direct]` (Q1);
   - `GatewayCall.routes` is required, passed from the spec by agents and the evaluation runner.
7. **Migration 0021:**
   - `usage_records.route` and `eval_runs.route` (text, NOT NULL DEFAULT `fake`, CHECK in `fake`, `direct`, `bedrock`), plus insert grants;
   - `eval_eligible` replaced by a version with a route parameter (the old signature dropped);
   - the schema-check maps and `DEFINER_FUNCTIONS` signature.
8. **The parity check** (`abacus_tools/route_parity.py`, `make route-parity ROUTE=…`), run with real credentials:
   - per catalog model: a structured call, a cached-prompt call (checks cache tokens), a batch API create-and-cancel, and the model ID resolving;
   - it writes `docs/operations/route-parity/<route>-<date>.json` and prints its SHA-256 for `route_parity` (D2).
9. **Embeddings:** `embedder()` picks `BedrockTitanEmbedder` when `embedding_provider` is `bedrock-titan` (route `bedrock`, with usage records carrying it).

**Protected paths (approval file):**
- `backend/src/abacus/ai_gateway/**` and `backend/src/abacus/modules/agents/**`;
- `backend/src/abacus/kernel/config.py` and `backend/migrations/**`;
- `backend/pyproject.toml`, `backend/uv.lock` and `Makefile`;
- `backend/src/abacus_tools/**` (evaluation runner, parity tool, schema maps);
- `backend/tests/unit/**` (pins);
- `docs/operations/**`.

### Questions for approval
- **D1. In synthetic environments (local and CI) every call uses the single `fake` route, and agent specs' route lists are validated but not applied?** *Recommendation: yes.* SPEC-010 AC-6 treats the fake as one route.
- **D2. Route enablement:**
  - parity is recorded in settings (`route_parity`: date and the report's SHA-256), and the gateway checks the 90-day window;
  - the CI cross-check that each deployed SHA matches a committed report waits for TASK-014, where deployed configuration first exists.

  *Recommendation: yes.* The container doesn't ship `docs/`.
- **D3. In non-synthetic environments every route, including the preferred tier's, needs a passing per-route evaluation (not only cheaper tiers)?** *Recommendation: yes.* This is ADR-073's enforcement line; evaluation mode itself isn't gated.
- **D4. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-07` — SPEC-010 approved and merged (#44). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Questions for the human
- Design questions D1–D4 (above).

## Handoff
