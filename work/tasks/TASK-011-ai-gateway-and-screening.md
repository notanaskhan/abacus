---
id: TASK-011
title: AI gateway, fake model and evidence screening
spec: SPEC-000
acceptance_criteria: [AC-14, AC-15, AC-16, AC-17]
risk_zone: red
status: in-progress
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

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
-

## Questions for the human
-

## Handoff
- **Current state:** Design drafted; awaiting founder approval (red). No code. Starts after TASK-010b merges.
- **Exact next step:** On approval, write `work/approvals/TASK-011.yaml` with these paths:
  - `.claude/hooks/_protected.py`, `.github/CODEOWNERS`, `docs/architecture/protected-paths.md`
  - `backend/pyproject.toml`, `backend/uv.lock`
  - `backend/src/abacus/kernel/**`, `backend/src/abacus/ai_gateway/**`
  - `backend/src/abacus/modules/agents/**`, `backend/src/abacus/modules/identity/**`, `backend/src/abacus/modules/evidence/**`, `backend/src/abacus/modules/connections/**`
  - `backend/src/abacus/worker/**`
  - `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`
  - `backend/tests/unit/quality/test_banned_patterns.py`
  - `evals/**`
  - plus `docs/architecture/permission-matrix.yaml` if Q2 takes the alternative.
