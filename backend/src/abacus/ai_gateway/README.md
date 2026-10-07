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

## Rules
- **No provider endpoints or SDKs outside this package** (PROVIDER-001).
- **No inline prompts** (PROMPT-001). Outside this package, nothing builds a `ModelRequest`, writes the instructions layer from a literal, or names a prompt that isn't `id@vN`.
- **Usage is attributed** to firm, engagement, agent, run and prompt version (AC-16). Inputs are logged by hash only.
