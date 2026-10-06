---
id: TASK-011
title: AI gateway, fake model and evidence screening
spec: SPEC-000
acceptance_criteria: [AC-14, AC-15, AC-16, AC-17]
risk_zone: red
status: in-review
branch: task-011-gateway
worktree:
created: 2026-10-06
updated: 2026-10-06
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
AI gateway with prompt registry, agent spec, context builder, fake model, output schema with one repair then escalate, handoff and citation verification, usage records; screening workflow triggered from the outbox; agents propose only.

## Scope
In:
- `abacus.ai_gateway`: provider abstraction, a fake model, prompt registry, call contract, schema validation with one repair then escalate, budget, usage records, logging;
- agent specs, with `evidence.screener` as the first;
- `AgentContext` in `authorise` (ADR-025 intersection);
- a context builder (five layers, untrusted wrapping);
- the `Handoff` base and typed `Citation`s, with a deterministic citation verifier;
- `agent_runs`, `screening_results`, `usage_records`;
- the screening workflow, started from the `evidence_version.created` outbox event;
- an evaluation suite scaffold with three synthetic cases.

Out: a real provider (Anthropic) and real model calls (a SPEC-000 non-goal); the evidence board UI (TASK-012); suggestions, follow-ups and the engagement agent.

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md`
- ADRs: ADR-005, ADR-019, ADR-047, ADR-050, ADR-051, ADR-052, ADR-054, ADR-065, ADR-066, ADR-070

## Plan
- [x] Plan approved by human (founder, 2026-10-06: "approved, proceed with your recommendations") — **red: founder reviews each PR line by line**
- [x] Approval file `work/approvals/TASK-011.yaml` written by the agent at the founder's instruction (2026-10-06); approved by founder: paths under *Approval file text*, expires 2026-10-27
- [x] Q1–Q5 recommendations approved:
  - the initiator is the human behind the triggering event;
  - the agent does not change request-item status (the screening result proposes it);
  - fake model only;
  - the relay runs in the worker;
  - split into 011a (gateway and agents) and 011b (screening workflow).
- Red task: the agent drafts the design here; the founder edits or approves it before any code, then reviews the diff line by line (founder decision 2026-10-06).

### Design (for founder review)

**1. AgentContext (ADR-005, ADR-025).**
- `AgentContext(tenant(actor_kind="agent", actor_id="agent:<agent_id>:<run_id>"), agent_id, agent_run_id, engagement_id, task_scope, initiator)`.
- Issued only by identity, from an `agent_runs` row (the same pattern as `SystemContext`).
- `authorise` gives an agent an action only if all three agree (the ADR-025 intersection):
  - the matrix's `agent` value (`task_scope` → the action is in the run's declared task scope);
  - the **initiator** (Q1) is allowed the action on that engagement, re-checked live;
  - the action is in the agent spec's task scope.
- Decision actions are denied by the matrix (`agent: deny`). Decision service functions also take only `AuthContext` (type-level) and check `actor_kind == "human"` at runtime (AC-17).

**2. AI gateway (`abacus.ai_gateway`; ADR-019, ADR-050, ADR-070).** One entry point:
`call(GatewayCall(purpose, prompt="evidence.screen@v0", tier, output_schema, budget_usd, actor: AgentContext, context: AssembledContext)) -> GatewayResult[T]`.
- Refuses calls missing a purpose, schema, budget, tenant or registered prompt.
- Renders the registered prompt with the assembled context and routes by tier to a `ModelProvider`. The only provider is `FakeModel` (local and test; scripted, deterministic).
- Validates the output against the Pydantic schema. If it's invalid: **one repair** call with the validation errors, then **escalate** (result status `escalated`, no output).
- **Budget:** the estimated cost of the call must be within `budget_usd`, and the actual cost is recorded.
- **ADR-050 guard:** refuses inputs containing a dataset over 200 rows.
- **One `usage_records` row per provider call (AC-16):** firm, engagement, agent, run, prompt id and version, model, tier, tokens in and out, cost, outcome, inputs hash.
- Logs carry model, prompt version, inputs hash and outcome. The output itself is stored on the agent run, not in logs.
- **Prompt registry:** `ai_gateway/prompts/<id>/<version>.txt`, plus an index. PROMPT-001 bans inline prompt strings at gateway call sites, and PROVIDER-001 already bans provider endpoints.

**3. Agent specs (ADR-047).**
- `modules/agents/specs/evidence.screener.yaml`, validated by a Pydantic `AgentSpec`:
  - id, purpose, prompt and version, tier and escalation tier;
  - input and output schemas;
  - task scope (`evidence.read`, `screening.run`);
  - limits (tokens, cost $0.03, steps 1, time);
  - autonomy `propose`;
  - untrusted inputs (account names);
  - evaluation suite.
- Specs live under the module (ADR-047's path predates ADR-101).
- The runtime refuses to start an agent without a valid spec. A test checks that every spec names an existing prompt version and evaluation suite.

**4. Context builder (ADR-051, ADR-052).**
- Five layers in order: instructions → firm context → engagement context → examples → task input. Each has a token budget; truncation is logged.
- Untrusted inputs, named by the spec, are wrapped automatically in labelled delimiters.
- Screening input is the request item description plus a **computed** trial-balance summary: totals, line count, period, entity, and account names (untrusted). No amounts per row (ADR-050).
- The context hash is stored on the agent run.

**5. Handoff and citations (ADR-054, ADR-066).**
- `Handoff(action, confidence, rationale, citations: list[Citation], unverified: list[str])`.
- `ScreeningOutput(Handoff)` with `action ∈ {ready_for_review, needs_revision}`.
- `Citation(cell: "B12", quote?: str, value?: Decimal)`. The verifier opens the evidence version's `.xlsx` and checks three things:
  - the cell exists;
  - the quote equals the cell's text;
  - the value equals the cell's number.

  Failures are marked `verified=false` and listed as unverified (AC-15).

**6. Tables** (migration `0010`; owners: agents and ai_gateway; all insert-only except `agent_runs.status`):
- `agent_runs`: agent, spec version, engagement, evidence version, initiator, source event, status, context hash, output (jsonb) and timestamps.
- `screening_results`: evidence version, agent run, action, confidence, rationale, citations (with verified flags), unverified. `created_by_kind = 'agent'` is a CHECK (AC-14).
- `usage_records`.

**7. Screening workflow (ADR-017, ADR-018).**
- The worker also runs the **outbox relay** loop. Its Temporal publisher maps `evidence_version.created` → start workflow `screening:<evidence_version_id>`, idempotent, so the relay's at-least-once delivery is safe.
- Activities:
  1. create the agent run (spec check; initiator resolved, Q1);
  2. build context;
  3. call the gateway;
  4. verify citations;
  5. record the screening result.

  Each loads its `AgentContext` from the run row, and failures end the run.
- A new module registry entry; no change to the retrieval workflow.

**8. Evaluation scaffold.**
- `evals/screening/` holds three synthetic cases: balanced, unbalanced-looking, and an adversarial account name.
- `make evals` runs them through the gateway with `FakeModel` today, and with real models later.
- Each run records cost per case.

### Questions for approval
- **Q1. Who is the initiator of an event-triggered agent?** ADR-025 intersects the agent's rights with its initiator's. Screening starts from `evidence_version.created`, and the system actor isn't allowed `evidence.read` in the matrix, so with the system as initiator the agent could never read the evidence. Recommend: **the human whose action caused the event**, taken from the delegation chain (the retrieval's `started_by`), re-checked live (an active membership that is allowed `evidence.read`). The chain is recorded on the agent run.
- **Q2. Request item status after screening.** SPEC-000's state table has "received → ready_for_review / needs_revision" done by the *Agent (proposal)*. The matrix gives agents no `request_item.mark_ready` (and ADR-005 says humans decide). Recommend: **the agent doesn't change the item's status.** The screening result *proposes* the status, the board shows it (AC-18), and a human marks it later. The alternative is a new matrix action, `request_item.propose_status` (agent: `task_scope`), a protected-matrix change.
- **Q3. Fake model only.** The `Provider` protocol plus `FakeModel`; a real Anthropic provider (allowlisted) arrives with the spec that turns on real calls. Recommend yes.
- **Q4. The relay runs inside the worker** as a loop every 2 seconds, until a dedicated relay process is needed. Recommend yes.
- **Q5. Split into TASK-011a and 011b**, as with 010:
  - 011a: the gateway, fake model, registry, specs, `AgentContext`, context builder, handoff, citations, usage records, tables;
  - 011b: the screening workflow, relay publisher, screening results, eval scaffold.

  Recommend yes.

### Interface contract — TASK-011a (tests written independently — ADR-078)
**Imports**
- `from abacus.ai_gateway import call, GatewayCall, GatewayResult, Attribution, GatewayRefused, BudgetExceeded, ContextBuilder, AssembledContext, DatasetTooLarge, ContextTooLarge, MAX_ROWS, MODELS, FakeModel, ModelRequest, ModelResponse, ProviderError, configure_provider, prompt, registry, UnknownPrompt, Prompt, cost, estimate_tokens` (each one is in `__all__`)
- `from abacus.modules.agents.api import AGENTS, AgentSpec, spec, SCREENER, Citation, Handoff, ScreeningOutput, VerifiedCitation, verify_citations, install_fake_responses, create_screening_run, load_agent_context, screen, fail_run, ScreeningOutcome, AgentRunNotRunning, SheetLayoutError`
- `from abacus.modules.agents.citations import facts, SheetFacts` (module-internal; unit tests only)
- `from abacus.modules.identity.api import AgentContext, agent_context_for_run, is_active_member, NoActiveTenant, agent_may_hold, authorise, visible, Resource, Forbidden`
- `from abacus.modules.evidence.api import CODE_COLUMN, NAME_COLUMN, DEBIT_COLUMN, CREDIT_COLUMN, FIRST_LINE_ROW, TOTAL_LABEL` (the rendered trial-balance layout)

**AgentContext and `authorise` (§1, ADR-025)**
- `await agent_context_for_run(*, tenant_id, run_id, agent_id, engagement_id, task_scope, initiator_user_id)`:
  - resolves the initiator's live active membership inside identity; none → `NoActiveTenant`. No function hands another module a person's `AuthContext`;
  - `tenant.actor_kind == "agent"`, `tenant.actor_id == f"agent:{agent_id}:{run_id}"`;
  - may be called only from `agents/service.py` (SYS-001); a hand-built `AgentContext(...)`, or `replace(agent, …)`, is CTX-001.
- The agent holds the role `agent` on its own engagement only. Another engagement or a firm resource → `Forbidden` at `relationship`.
- `task_scope` grants an action only if the run's `task_scope` contains it; otherwise `Forbidden` at `role`. `agent: deny` actions (`evidence.accept`, `evidence.reject`, `fulfilment.confirm`, `suggestion.resolve`, …) → `role`, whatever the scope.
- **Intersection, checked live:** the initiator must also be allowed the action on that engagement, otherwise `Forbidden` at `delegation`.
  - For an action no human role holds (agent and system only, e.g. `screening.run`), the initiator must instead be allowed `AGENT_ONLY_REACH` (`evidence.read`).
  - Covers: an initiator removed from the engagement, an initiator who is a `reviewer`-only member where the action needs more, and an archived engagement (writes → `attribute`).
- `visible(agent, read_action, col)` = the agent's engagement AND what the initiator can see.
- Logs carry `agent_id`, `agent_run_id`, `on_behalf_of`.
- `is_active_member(tenant_id, user_id)` → whether the person has an active membership in that firm now.
- `agent_may_hold(action)` is True iff the matrix says `agent: task_scope`.

**Prompt registry**
- `prompt("evidence.screen@v0")` → `Prompt(id="evidence.screen", version="v0", text, sha256)` with `.ref == "evidence.screen@v0"`.
- An unknown or malformed reference → `UnknownPrompt`. `registry()` lists every `prompts/<id>/<version>.txt`.

**ContextBuilder (§4)**
- Layers are always rendered in the order instructions, firm, engagement, examples, task. Empty layers are omitted. Each layer renders as `## <name>\n<text>`.
- Budgets are in tokens (4 chars each; defaults instructions 1000, firm 500, engagement 500, examples 1000, task 4000). Non-task text over budget is cut and listed in `.truncated`.
- `.text("task", …)` and `.text("instructions", …)` → `ValueError`. Instructions are the registered prompt's, sent as the system message.
- `.task(data, untrusted=names, trim=None)`:
  - trusted fields are rendered as one JSON line;
  - each untrusted field is rendered as `<untrusted name="x">\n<json>\n</untrusted>`, with `<` escaped so content can never close the block;
  - any list longer than `MAX_ROWS` (200) → `DatasetTooLarge`;
  - over the task budget: drops items from the end of list `trim` until it fits (task layer listed in `.truncated`), else `ContextTooLarge`;
  - the task layer is never cut mid-text.
- `.sha256` is the SHA-256 of `render()`: deterministic for equal inputs, different when any layer differs.

**Gateway `call` (§2)**
- `GatewayRefused` (and nothing recorded) for:
  - a blank purpose;
  - a non-Pydantic `output_schema`;
  - `budget_usd <= 0`;
  - an unknown tier;
  - an attribution without a `TenantContext` or `agent_id`;
  - an unregistered prompt.
- The provider gets `ModelRequest(model=MODELS[tier][0], system=<prompt text>, user=context.render(), max_output_tokens, prompt_ref)`.
- Valid JSON for the schema → `status="ok"`, `attempts=1`.
- Invalid, then valid → `"repaired"`, `attempts=2`; the second request's user text holds a `## repair` section with the validation errors.
- Invalid twice → `"escalated"`, `output=None`.
- **Budget:** before each attempt, the estimated cost (`cost(tier, estimate_tokens(system+user), max_output_tokens)`) plus what was spent must be ≤ `budget_usd`. With an `agent_run_id`, the budget is the run's: the `cost_usd` of that run's earlier usage records (including retried `screen` calls) counts too.
- `call` must not run inside a unit of work; it commits usage per attempt. On the first attempt → `BudgetExceeded`; on the repair → `escalated`. Either way a `budget_refused` usage row is recorded.
- `ProviderError` is recorded as `provider_error` and re-raised.
- **One `usage_records` row per attempt:**
  - tenant, engagement, agent_id, agent_run_id, prompt_id, prompt_version, model, tier, input and output tokens, `cost_usd`, `outcome ∈ {ok, invalid, repaired, budget_refused, provider_error}` and `inputs_hash` (sha256 of `"<ref>\n<user>"`);
  - each row comes with an audit event `model.called` by the attribution's actor.
- `cost` uses the per-million prices in `MODELS`, quantised to 0.000001.
- `FakeModel` outside local and test → `RuntimeError`. A prompt with no responder → `ProviderError`.

**Agent specs (§3)**
- `AGENTS["evidence.screener"]`: prompt `evidence.screen@v0`, tier `small`, task scope `{evidence.read, screening.run}`, autonomy `propose`, `confidence_routing.below=0.5 → needs_revision`, untrusted inputs `{account_names}`.
- Invalid specs fail at import:
  - unknown keys or an unregistered prompt;
  - a task scope holding an action the matrix doesn't give agents as `task_scope`;
  - `autonomy` other than `propose`.
- `spec(unknown)` → `LookupError`.
- Every spec's `evaluation_suite` path exists, or a test lists it as owed to 011b.
- `python -m abacus_tools.codegen.agent_specs --check` passes, and fails after a YAML edit.

**Handoff and citations (§5)**
- `Citation.cell` must match `^[A-Z]{1,3}[1-9][0-9]{0,6}$`; a quote is at most 200 characters; extra keys are rejected.
- `ScreeningOutput.action ∈ {ready_for_review, needs_revision}`; `confidence` in [0, 1]; `rationale` 1–2000 characters.
- `verify_citations(xlsx_bytes, citations)` returns one `VerifiedCitation` per citation:
  - `cell_not_found` for a cell outside the sheet or empty;
  - `quote_mismatch` when the quote differs from the cell text;
  - `value_mismatch` when the value differs from the cell number;
  - otherwise `verified=True`.
- `facts(xlsx_bytes)` is strict and uses the evidence layout constants:
  - exactly one Total row (blank code column, `TOTAL_LABEL` in the name column);
  - every row from `FIRST_LINE_ROW` to the Total row has an account code and two amounts;
  - no amount appears after the Total row;
  - anything else → `SheetLayoutError` (a `ValueError`). Examples: no Total row, two Total rows, a blank-code line named `Total` above the real one, a missing amount;
  - `total_debit` and `total_credit` are summed by code from the line rows, and `total_row_matches` compares them with the sheet's own Total row;
  - `line_count` and `account_names` come from the line rows. An account named `Total` with a code is an ordinary line.

**Agents service (§6, Q1, Q2)**
- `evidence_version.created` now carries `requested_by`. A retrieval sets it to the run's `on_behalf_of`; the default is None.
- `create_screening_run(tenant_id, evidence_version_id, source_event_id, requested_by)`:
  - `requested_by=None`, a person without an active membership in the firm, or a version without a snapshot → `None`, with nothing written (never an error that an at-least-once event would retry forever);
  - the audit actor of `agent_run.started` is `agents:evidence.screener`;
  - otherwise inserts an `agent_runs` row (status `running`, `spec_version`, `task_scope` from the spec, `initiator_user_id=requested_by`) and records `agent_run.started`;
  - the same `(agent, source_event_id)` again → the same run id, with no new row or audit event.
- `load_agent_context(tenant_id, run_id)`:
  - an unknown run → `NotFound`;
  - a finished run → `AgentRunNotRunning(status)`;
  - an initiator without an active membership → `NoActiveTenant`;
  - the context's task scope is the run's `task_scope` ∩ the current spec's;
  - a run whose `spec_version` differs from the spec → run failed (`spec_version_changed`) and `AgentRunNotRunning("failed")`.
- `fail_run(tenant_id, run_id, code)` ends a running run as `failed` with that code and records `agent_run.failed`. It returns True. On a run that has already ended it returns False and writes nothing.
- `screen(agent)` with `install_fake_responses(FakeModel())` on a retrieved trial balance:
  - `status="completed"`, and one `screening_results` row with `created_by_kind='agent'` (AC-14), the action, confidence, rationale, verified citations and `unverified`;
  - the run is `completed` with `context_hash` and `output`;
  - audit events `model.called` and `screening_result.created`, by actor `agent:evidence.screener:<run>`;
  - one `usage_records` row with `outcome=ok` (AC-16);
  - the request item's status is unchanged (Q2);
  - the model's context contains no per-line amounts, only totals (ADR-050);
  - account names appear only inside `<untrusted name="account_names">`.
- A responder citing a wrong value or a non-existent cell → the result is still recorded, with `verified=false` and a reason, and the citation is listed in `unverified` (AC-15).
- Invalid output twice → run `escalated`, no `screening_results` row, audit event `agent_run.escalated`.
- A confidence below 0.5 → action `needs_revision`, whatever the model proposed.
- Code overrides the model (ADR-066). The action is forced to `needs_revision`, and a note added to `unverified`, when:
  - any citation fails verification;
  - the line debits and credits differ;
  - the sheet's Total row differs from its lines.

  When the account list was trimmed to fit the budget, `unverified` notes it and the action is kept.
- Terminal errors in `screen` fail the run, then re-raise:
  - `SheetLayoutError` → `unreadable_evidence`;
  - `DatasetTooLarge`/`ContextTooLarge` → `context_too_large`;
  - `BudgetExceeded` → `budget_exceeded`;
  - `GatewayRefused` → `gateway_refused`;
  - `Forbidden` → `forbidden`;
  - `NotFound` → `not_found`.

  `ProviderError` leaves the run `running`, so it can be retried.
- Screening the same run twice → the second raises `AgentRunNotRunning`, and there is still one result.
- An initiator removed from the engagement before `screen` → `Forbidden` (`delegation`), with no result; the run is failed (`forbidden`).
- Database: `screening_results` and `usage_records` are insert-only for `abacus_app`. `agent_runs` is forward-only: a finished run can't be updated; `context_hash` and `output` are write-once.
  - A screening result's `evidence_version_id` must be its run's.
  - A usage record's `engagement_id` must be its run's (composite foreign keys).

**Rules**
- **PROMPT-001** flags, outside `ai_gateway`, with import aliases and keyword forms counting:
  - `ModelRequest(...)`;
  - `.text("instructions", …)` and `.text(layer="instructions", …)`;
  - `GatewayCall` whose prompt (second positional argument or `prompt=`) is an f-string, a concatenation, or a literal not matching `id@vN`.
- **AGENT-001:** for any action the matrix gives agents no grant for (no `agent` entry, or `deny`), `authorise(x, action, …)` is flagged unless `x` is a parameter typed `AuthContext` or `SystemContext`. Covers aliased `authorise` and the `ctx=`/`action=` keywords.
- **BOUND-002:** agents depend on identity, engagements, organisations, evidence and requests only.

### Approval file text
```yaml
task: TASK-011
approved_by: founder
expires: 2026-10-27
paths:
  - .claude/hooks/_protected.py
  - .github/CODEOWNERS
  - docs/architecture/protected-paths.md
  - backend/pyproject.toml
  - backend/uv.lock
  - backend/src/abacus/kernel/**
  - backend/src/abacus/ai_gateway/**
  - backend/src/abacus/modules/agents/**
  - backend/src/abacus/modules/identity/**
  - backend/src/abacus/modules/evidence/**
  - backend/src/abacus/modules/connections/**
  - backend/src/abacus/worker/**
  - backend/src/abacus_tools/quality/schema_check.py
  - backend/src/abacus_tools/quality/banned_patterns.py
  - backend/tests/unit/quality/test_banned_patterns.py
  - evals/**
reason: TASK-011 — AI gateway, agent specs and context, citations, usage records, screening workflow
```

### Steps
1. Approval file. Protect `ai_gateway/**` and `modules/agents/**`.
2. Migration `0010` and `schema_check`. `AgentContext` in identity/authz.
3. The gateway (provider, fake, registry, call, budget, usage, logging) and rules PROMPT-001 and AGENT-001 (decision functions human-only).
4. Agent specs, context builder, handoff and citation verifier.
5. (011b) Relay publisher, screening workflow and activities, screening results, evals.
6. For each part: contract → independent tests → two reviews → `make check` → PR (red, line by line).

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|

## Progress log
- `2026-10-06` — Created from the SPEC-000 breakdown approved by the founder. Not started.
- `2026-10-06` — Design drafted (§1–8, Q1–Q5) for founder review, while TASK-010b (PR #11) awaits review.
- `2026-10-06` — Approved with all recommendations; approval file written at the founder's instruction. 011a started on `task-011a-gateway` from main (it doesn't depend on 010b).
- `2026-10-06` — 011a implemented: gateway, context builder, prompts, specs, handoff and citations, the agents service, PROMPT-001 and AGENT-001. Smoke-tested end to end with the fake model. The founder chose the reach rule for agent-only actions (`screening.run`): the initiator must hold `evidence.read` (ADR-025 clarified). The initiator is now carried on `evidence_version.created` (`requested_by`), and screening figures are computed from the evidence sheet, so agents doesn't depend on ledger or connections. Contract written; independent tests and reviews next.
- `2026-10-06` — The security review found one blocker, now fixed: a spoofed Total row could hide an unbalanced trial balance. Fixed with it: should-fix items from both reviews, applied to the code and to the contract above. The first test author stalled; its partial integration tests are carried forward.
- `2026-10-06` — PR #11 merged; TASK-011a rebuilt on main as `task-011a-ai-gateway` (a force-push of the old branch was refused; `task-011a-gateway` is stale). The independent tests found 3 bugs, all fixed: `fail_run` passed a text code to an audit `Ref` (the code now lives only on the row, as for sync runs); an archived engagement denied agent writes at `delegation` instead of `attribute`; SYS-001 let `connections/service.py` issue agent contexts (the rule now allows each issuer only its own function).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Agent-only actions: the initiator must hold `evidence.read` (reach rule) | No human role holds `screening.run`, so a strict intersection always denies (founder, 2026-10-06) | ADR-025 clarified |
| Initiator = `requested_by` on `evidence_version.created` | Keeps agents independent of connections; covers uploads too | No |
| Screening totals are summed from the evidence sheet, not the ledger | The pinned architecture tests say only connections depends on ledger; this also screens what reviewers see | No |
| The task layer trims a named list or refuses; it is never cut mid-text | Cutting could sever an `<untrusted>` block | No |

## Gotchas and discoveries
- 011b: `screen` is one activity. A retry after a failed final write calls the model again; the spend counts against the run's budget.
- 011b: the spec fields `limits.max_steps`, `limits.max_seconds`, `escalation_tier`, `input_schema` and `output_schema` are validated but not yet enforced. Enforce them, or drop them, when the workflow lands.
- 011b: `requested_by` is trusted from the `evidence_version.created` event, which is written in the same transaction as the version. The workflow must take it from the relayed event only. Manual uploads don't pass it yet, so they aren't screened.
- 011b: `agent_context_for_run` builds the initiator with `mfa_at=None`, so an agent can never be delegated an `mfa_recent` action.
- Later: the `ai_gateway` table-ownership rule (OWN-001 covers only `modules/*`). Screening checks the sheet against itself, not against the ledger; a ledger cross-check is possible later.

## Questions for the human
-

## Handoff
- **Current state:** TASK-011a PR open from `task-011a-ai-gateway` (rebuilt on main after PR #11; `task-011a-gateway` is stale and can be deleted). The independent tests found 3 bugs, all fixed. Unit tests pass locally. Local integration runs were blocked by a Docker VM clock skew (S3 `RequestTimeTooSkewed`), so CI is the gate.
- **Exact next step:** Confirm CI, then the founder's line-by-line review (red). Merge (rebase), then TASK-011b: the relay publisher in the worker, the `screening:<evidence_version_id>` workflow running `screen` as one activity (`fail_run` on terminal errors), `requested_by` from the relayed event only, and the evals scaffold. See Gotchas.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none known.
- **Open issues:** branch protection off; the Gotchas list the 011b items.
