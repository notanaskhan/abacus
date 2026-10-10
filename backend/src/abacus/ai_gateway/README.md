# ai_gateway

The only path to a model (ADR-019, ADR-050, ADR-052, ADR-057, ADR-070). Owns `usage_records` (ADR-103). PROTECTED.

## Public interface (`__init__.py`)
- `call(GatewayCall) -> GatewayResult`:
  - refuses a call without a purpose, output schema, tier, budget, attribution or registered prompt (`GatewayRefused`);
  - bounds each provider call by `timeout_seconds` (a timeout is recorded as `provider_error` and raised as `ProviderError`);
  - checks the budget before every attempt (`BudgetExceeded` on the first). For an agent run the budget is the run's: earlier usage for the run counts;
  - validates output against the schema, repairs once, then escalates (`output=None`);
  - records one `usage_records` row and a `model.called` audit event per attempt, each in its own unit of work. Never call it inside one.
- `ContextBuilder`: five layers in fixed order (instructions, firm, engagement, examples, task), each with a token budget. The instructions layer is refused: instructions are the registered prompt's.
  - Untrusted task fields become JSON `<untrusted>` blocks.
  - More than `MAX_ROWS` rows raises `DatasetTooLarge`.
  - The task layer is never cut mid-text. `trim=` names a list to shorten from the end; otherwise `ContextTooLarge`.
- `prompt(ref)`, `registry()`, `UnknownPrompt`, `estimate_tokens`: prompts live in `prompts/<id>/<version>.txt`; a reference is `id@vN`.
- `ModelProvider`, `configure_provider`, `FakeModel` (local and test only), `ProviderError`, `MODELS` (tier to model and prices).

- `NotAdmitted(reason, retry_after)`: a call refused admission (`admission.py`; ADR-072, SPEC-003). `GatewayCall` requires `work_class` and `essential`, and may list `cheaper_tiers`.

## Admission (ADR-072; SPEC-003 AC-9 to AC-12)
- Before every attempt, the call takes one request and its estimated tokens from its model's bucket (`provider_capacity`, migration 0014). The bucket is shared by every process and reached only through SECURITY DEFINER functions. It commits without audit events (founder decision 2026-10-07; UOW-001/002 exempt `admission.py`).
- **Priority by reserve:** a class may take capacity only above its reserve (`work_classes[c].admission_reserve_pct`: 0, 0, 25, 50). A non-essential call uses the next class's reserve.
- **Refused:** background and batch calls are deferred (`NotAdmitted("deferred")`) and never stepped down. Interactive and time-sensitive calls try the spec's `cheaper_tiers`, then raise `NotAdmitted("provider_capacity")`. The workflow waits and asks again; the gateway never loops. A call needing more tokens than its class may ever take raises `CallTooLarge`.
- **Estimate:** the input estimate plus `max_output_tokens`, not settled against actual use. The bucket is over-reserved, and the 80% limits cover a heuristic under-estimate.
- **Repair attempts:** a refusal on the repair attempt discards the first response, and the next ask starts over. The budget still holds (`_spent_by_run`).
- **Boot check:** `check_provider_limits()` (worker boot) refuses to start outside local and test when any model has no limits.
- **Rate limits:** a `ProviderError(rate_limited=True)` blocks the model for `retry_after` (a finite value clamped to 1–3,600 s; otherwise 30 s), records usage `rate_limited` (spending nothing), and raises `NotAdmitted`. If the block itself fails, the call still waits. It is never retried here.
- **Fail closed:** an unknown model, or an unreachable bucket, admits nothing.
- **Telemetry:** an `ai.admit` span, and the counter `abacus.admission` (provider, model, class, outcome, reason).

## Evaluation (SPEC-005; TASK-020)
- **`evaluation(tier)`:** a context manager that pins the tier of the block's calls. Only the evaluation runner uses it.
- **`eligible(tenant, agent_id, tier, model, prompt_version)`:** asks `eval_eligible`, a SECURITY DEFINER function (migration 0016). It is true only if the latest finished run for that key passed on a real model. It fails closed.
- **Cheaper tiers:** in admission, an entry after the call's own tier is tried only if it is eligible; otherwise it is skipped (`admission.tier_ineligible`). No tier is eligible until real-model runs are published (TASK-014).

## Budgets (ADR-069; SPEC-007; TASK-022)
`budgets.check_budget` runs before every attempt, after the run's budget and before admission:
- **Levels:** the engagement's month, the firm's month (`budgets` row, else the default) and the platform's day (`platform_spend_today()`, SECURITY DEFINER).
- **Soft limit:** deferrable work gets `NotAdmitted("deferred")` and waits; the alert is raised once per level and period.
- **Hard limit:** deferrable work raises `BudgetExhausted`; the platform's hard limit stops all work.
- **Failure:** if the sums can't be read, deferrable work is refused (fail closed).

Sums are cached for 5 s per process and dropped after each recorded call. `run_anomaly_job` runs hourly in the worker, beside the relay.

## Embeddings (SPEC-009; TASK-024)
`embed(EmbedCall)` is the only path to an embedding model. Before the provider is called, the call passes, in order:
1. its own budget, checked on an estimate;
2. the budget hierarchy;
3. admission on the embedding model.

Each provider call writes a usage record (`prompt_id` `embed`, tier `small`).

The provider sits behind `EmbeddingProvider`. `FakeEmbedder` (deterministic, hashed word features, 1,024 dimensions) is used in synthetic environments when none is configured. The real provider comes with ADR-073.

## The data boundary (SPEC-026; TASK-049; ADR-031)
A real model sees synthetic data only, until provider terms (zero retention, no training) are recorded and staging exists.
- **Settings:** `model_data_boundary` has one value, `synthetic_only`. A real route (or the real embedding provider) is refused in `staging`, `production` and `test`, and in `local` unless `allow_real_model_locally`. Every real-route model ID must be pinned (no `latest`).
- **Per call:** `enforce_boundary` runs before both provider calls (`_call`, `embed`). Any route other than `fake` needs the call's firm to be synthetic, answered by identity through `register_synthetic_tenants` (unregistered means refused, cached 60 s). A refusal raises `DataBoundaryRefused` (never retried or rerouted), audits `ai.boundary_refused` and counts `abacus.ai.boundary_refused`.
- **Who's synthetic:** `firms.synthetic`, set only by the local seed and the evaluation stack as the owner; the app can't write it.

## Model routes (SPEC-010; ADR-073; TASK-025)
The same model family is reachable through two routes, `direct` (the provider's API) and `bedrock` (Amazon Bedrock in our AWS account). `fake` serves synthetic environments only.

**Configuration:**
- each tier's model ID per route lives in `settings().model_catalog`;
- each agent spec lists its allowed `routes` in order (the screener: `[bedrock, direct]`).

**When a route can be used:**
- it is in `model_routes`;
- it has a parity report from the last 90 days (`route_parity`; run `make route-parity ROUTE=…`);
- outside synthetic environments, the agent has passed its evaluation on that route.

**Admission:** admission walks tiers, then routes. Capacity and blocks are keyed by route and model.

**Failover within an attempt:**
- a 429 blocks that route's model for the provider's wait;
- an outage blocks it for `outage_block_seconds`;
- a 401 or 403 is logged as `provider.auth_failed` and leaves the route out for this call.

The attempt then moves to the next usable route. When none is left, the call waits (`NotAdmitted`) or fails (`ProviderError`).

**Where things live:**
- provider SDKs are imported only in `routes/` (ruff TID251; STORE-001 allows boto3 in `routes/bedrock.py` and `routes/parity.py`);
- usage records and spans carry the route;
- `embedding_provider = bedrock-titan` switches embeddings to Titan v2 on Bedrock.

## Prompt rollouts (SPEC-011; TASK-026)
A variant flag named `prompt.<agent_id>` (in `docs/architecture/feature-flags.yaml`) may switch one firm to another prompt version.

**When the flag is honoured:**
- the prompt must be registered;
- outside synthetic environments, the agent must have passed its evaluation for that prompt version on its first usable route. `EVAL_SUITES` keys on the agent's own prompt, so a variant counts as eligible only after the suite is regenerated for it.

**When it isn't:** the call keeps its spec's prompt, and `flag.variant_rejected` is logged and counted. Evaluation runs ignore the flag.

## Rules
- **No provider endpoints or SDKs outside this package** (PROVIDER-001).
- **No inline prompts** (PROMPT-001). Outside this package, nothing builds a `ModelRequest`, writes the instructions layer from a literal, or names a prompt that isn't `id@vN`.
- **Usage is attributed** to firm, engagement, agent, run and prompt version (AC-16). Inputs are logged by hash only.
