---
id: SPEC-010
title: Model routes, with a second route configured
status: draft
owner: founder
risk_zone: red
related_adrs: [ADR-073, ADR-019, ADR-072, ADR-069, ADR-070, ADR-055, ADR-057, ADR-097]
related_specs: [SPEC-003, SPEC-005, SPEC-007, SPEC-009]
created: 2026-10-07
updated: 2026-10-07
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
ADR-073 says every model is reachable through two routes to the same model family:
- **`direct`:** the provider's own API;
- **`bedrock`:** a major cloud platform inside our AWS trust boundary.

The gateway gets a route abstraction with real adapters for both. Each agent's spec lists its allowed routes in order. When a route fails or runs out of capacity, the call moves to the next allowed route, with no change of model and therefore no change of behaviour. A route counts as configured only after a parity check (prompt caching and batch processing) passes on it.

This finishes the Foundation layer's "model route abstraction with second route configured" (build plan §5.3). It also supplies SPEC-009's real embedding provider.

## 2. Problem and context
Today the gateway has one provider slot, filled by `FakeModel`. Tiers map to fake model names, and there is no real adapter. One outage at the provider would stop every agent.
- **What ADR-073 rules out:** switching model family on failure, because it changes outputs and invalidates evaluations.
- **What it requires instead:**
  - the same model through a second route, after verifying feature parity;
  - per-agent route configuration;
  - an evaluation run per allowed route and model.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| `ai_gateway` | Chooses the route per attempt; the only code that imports provider SDKs (ADR-019) |
| Agent specs | List allowed routes in preference order |
| Platform operators | Hold credentials; run the parity check; enable a route |
| The evaluation runner | Runs each suite per route and model (SPEC-005) |

## 4. Goals and non-goals
**Goals**
- **The route model:**
  - a `Route` is `direct` or `bedrock`;
  - each tier names one logical model, such as `claude-sonnet`, with a model ID per route, all in settings;
  - prices are per logical model, the same on both routes unless settings say otherwise.
- **Adapters:**
  - `AnthropicDirect` and `AnthropicBedrock` use the `anthropic` SDK (allowlisted, `ai_gateway` only). Bedrock signs through the SDK's Bedrock client with the task's IAM role.
  - Both implement `ModelProvider`, and `FakeModel` stays for synthetic environments.
  - Errors are normalised into `ProviderError(retryable, rate_limited, retry_after)`.
- **Routing per attempt:**
  - admission walks the agent's allowed routes in order for the call's tier, skipping any route that is disabled, blocked or not yet eligible;
  - capacity and blocks are already keyed by provider and model (SPEC-003), with the route as the provider.
- **Failover:**
  - a rate limit blocks that route's model (as today), and the call is admitted on the next route without waiting;
  - an outage (5xx, timeout, connection failure) blocks the route's model briefly (Q3), and the retry attempt uses the next route.
- **Attribution:**
  - usage records carry the route (ADR-070);
  - evaluation runs carry the route, and eligibility is per agent, route, tier, model, prompt and suite (ADR-073 enforcement).
- **Parity check:** `make route-parity` (real credentials) checks, per route, a structured call, prompt caching, the batch API, and the model ID's existence. It records a parity report. A route can be enabled only with a passing report (Q2).
- **Real embeddings:** `BedrockTitanEmbedder` (Amazon Titan Text Embeddings v2, 1,024 dimensions) behind SPEC-009's `EmbeddingProvider`, Bedrock route only (Q5).

**Non-goals**
- **Failover to another model family:** allowed by ADR-073 only per agent with passing evaluations; a later spec.
- **Batch-API execution of agent work:** this spec only verifies parity.
- **Live staging configuration:** credentials, IAM and the Bedrock model access request need the TASK-014 inputs (Q4). This spec builds and tests everything with fakes and recorded responses, so turning it on is configuration.

## 5. User stories and acceptance criteria
### Story 1: An outage doesn't stop the product
- **AC-1** Given an agent allowed `[bedrock, direct]` and the bedrock route returning 5xx or timing out, when it calls the gateway, then the failed attempt is recorded (`provider_error`, route `bedrock`), bedrock's model is blocked for the outage window (Q3), and the retry is admitted on `direct` with the same logical model and prompt. The result records route `direct`.
- **AC-2** Given a route answering 429 with `retry-after`, then that route's model is blocked for that long (as today), and admission tries the next allowed route at once. Only when every allowed route is blocked or full does the call wait (`NotAdmitted`, SPEC-003).
- **AC-3** Given every allowed route failing, then the call fails as today (`ProviderError`), with no model-family switch.

### Story 2: Routes are earned, not assumed
- **AC-4** Given an agent spec, then it declares `routes` (a non-empty, ordered subset of the enabled routes), validated at load. A call never uses a route its agent didn't list.
- **AC-5** Given a route not enabled in settings, or enabled without a passing parity report for its models, then no call is admitted on it. `make route-parity` writes the report (`docs/operations/route-parity/<route>-<date>.json`, identifiers and results only), and enabling checks the report's fingerprint (Q2).
- **AC-6** Given a non-synthetic environment, when a call would use a route on which its agent has no passing evaluation run for this tier, model, prompt version and suite (SPEC-005, now per route), then that route is skipped. In synthetic environments the fake model counts as one route, so this check doesn't apply.

### Story 3: Every call says how it went
- **AC-7** Given any model or embedding call, then its usage record names the route, and metering (SPEC-007) can split spend by route. Spans carry `ai.route`.
- **AC-8** Given the adapters, then provider SDKs are imported only in `ai_gateway/routes/` (an existing ban, narrowed), and credentials come only from settings (secret) or the IAM role, never from code or logs.

### Story 4: Real embeddings
- **AC-9** Given `embedding_provider = bedrock-titan`, then `ai_gateway.embed` calls Titan v2 on Bedrock with 1,024 dimensions and normalisation, with the same budget, admission and usage records as SPEC-009 (route `bedrock`).

## 6. Behaviour and flows
1. **Before an attempt:** take the routes the agent spec allows, minus any route that is disabled, has no parity report, or is not eligible (AC-6).
2. **Admission:** for each route in order, ask `admit(route, model_id, …)` (SPEC-003). The first route admitted is used. Cheaper-tier step-down (SPEC-005) still applies, per route, after every route of the preferred tier.
3. **The call:**
   - on success, record usage with the route;
   - on a 429, block that route's model for `retry-after`, and the next attempt starts again at step 1;
   - on an outage error, block that route's model for the outage window, and the next attempt starts again at step 1;
   - attempts stay limited to 2 per call, as today.

## 7. Domain and data changes
- **`usage_records.route`** and **`eval_runs.route`:** text, `direct`, `bedrock` or `fake`. Existing rows are `fake`. `eval_eligible` gains a route parameter, and the old signature is dropped.
- **No new tables.** `provider_capacity` already keys on (provider, model), and its provider becomes the route.
- **Settings:**
  - `model_routes` (enabled routes in order);
  - `model_catalog` (tier → logical model → per-route model ID and price);
  - `anthropic_api_key` (secret, for the direct route only);
  - `bedrock_region`;
  - `outage_block_seconds` (Q3);
  - `embedding_provider` (`fake` or `bedrock-titan`).
- **Agent specs** gain `routes`.

## 8. Interfaces
| Interface | Purpose |
|---|---|
| `ai_gateway.routes.{direct,bedrock}` | Adapters implementing `ModelProvider` (and `EmbeddingProvider` for Titan) |
| `make route-parity` | The parity check with real credentials; writes the report |
| `GatewayResult.route` | The route that answered |

No HTTP routes.

## 9. Authorisation and tenancy
No change to the matrix. Credentials are platform secrets, with no per-tenant keys for providers. Usage records stay tenant-scoped.

## 10. AI behaviour
The same model family on every route, so outputs don't change by design. Evaluations run per route (AC-6) to prove it, and a route whose evaluation fails is skipped for that agent.

## 11. Integrations
- **Direct:** Anthropic's Messages API.
- **Bedrock:** Amazon Bedrock runtime (Claude models and Titan Text Embeddings v2) in `bedrock_region`.

Both use the `anthropic` SDK and `boto3` (both allowlisted). Both are tested with `httpx.MockTransport` and recorded responses, so CI needs no new dependency and no network.

## 12. Edge cases and failure modes
- **The two routes disagree on a feature:** the parity check fails, and the route stays disabled (AC-5).
- **Model IDs lag on Bedrock** (a new model not yet available there): the catalog entry has no Bedrock ID, so that tier runs on `direct` only. This is visible in the parity report.
- **Both routes are blocked:** the call waits through admission (SPEC-003). Interactive work shows `queued` with its reason.
- **Credential failure (401 or 403):** not retryable, and the route is not blocked. It is an operator alert, and the call fails over to the next route for this attempt.
- **Partial streaming:** not used; calls are non-streaming.

## 13. Security and privacy
- **Data path:** the Bedrock route keeps data inside our AWS account and region. The direct route sends prompts to the provider under its data processing agreement and zero-retention terms (counsel, ADR-097). Which route is primary is Q1.
- **Credentials:** the API key sits in Secrets Manager and Bedrock uses the IAM role. Both are redacted from logs and never in spans.
- **Logging:** no prompt or completion text is logged on any route.

## 14. Audit trail and evidence integrity
Usage records (insert-only) gain the route. Parity reports are committed files with their fingerprint.

## 15. Observability
- **Metrics:** calls, errors and latency by route; failovers by reason; routes blocked.
- **Alerts:** a route blocked for an outage more than 3 times in 10 minutes, and any 401 or 403.

## 16. Performance and scale
Routing adds one admission check per route tried, which is milliseconds. Failover saves the wait that a single route would impose.

## 17. UX
None.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-3 | unit + integration | Fake routes injecting 5xx, timeout and 429; failover order; blocks; no family switch |
| AC-4 to AC-6 | unit | Spec validation; disabled or unverified routes skipped; per-route eligibility |
| AC-7, AC-8 | unit + lint | The route in usage records and spans; the SDK import ban narrowed to `ai_gateway/routes/` |
| AC-9 | unit | The Titan adapter against recorded responses |
| Adapters | unit | Request and response mapping, and error normalisation, on `httpx.MockTransport` |

## 19. Rollout
- **Local and CI:** the fake route only.
- **Staging (after TASK-014):** both routes enabled once `make route-parity` passes, and per-route evaluation runs for the screener.
- **Rollback:** the migration is additive (the route columns), and `model_routes` can drop a route at once.

## 20. Open questions
- [ ] **Q1: which route is primary.** *Recommendation:* `bedrock` first, `direct` second for every agent. Data stays in our AWS trust boundary by default. Direct carries outages and Bedrock model-availability gaps.
- [ ] **Q2: what enables a route.** *Recommendation:* the route appears in `model_routes`, and a committed parity report for its catalog models passed within the last 90 days. Enabling or disabling is an operator settings change.
- [ ] **Q3: outage handling.** *Recommendation:* any 5xx, timeout or connection error blocks that route's model for 30 seconds (`outage_block_seconds`), and the retry fails over. A 401 or 403 doesn't block, alerts, and fails over for that attempt.
- [ ] **Q4: the TASK-014 dependency.** *Recommendation:* build and test everything now with fakes and recorded responses. Enabling the real routes in staging waits for the AWS account, Bedrock model access, the Anthropic API key, and the counsel-reviewed terms (ADR-097).
- [ ] **Q5: embeddings route.** *Recommendation:* Titan v2 on Bedrock only, with no second route. A Titan outage pauses ingestion (batch work waits) and fails searches with 503. A second embedding route would need re-embedding into a separate vector space, which is deferred.

## 21. Future / explicitly deferred
- Cross-family failover with per-agent evaluations.
- Running batch-API agent work.
- Streaming.
- A second embedding route.
- Automatic parity re-checks on a schedule.
