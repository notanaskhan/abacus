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

## Rules
- **No provider endpoints or SDKs outside this package** (PROVIDER-001).
- **No inline prompts** (PROMPT-001). Outside this package, nothing builds a `ModelRequest`, writes the instructions layer from a literal, or names a prompt that isn't `id@vN`.
- **Usage is attributed** to firm, engagement, agent, run and prompt version (AC-16). Inputs are logged by hash only.
