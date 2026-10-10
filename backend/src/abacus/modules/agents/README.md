# agents

Agent specs, agent runs and screening (ADR-005, ADR-025, ADR-047, ADR-050, ADR-054, ADR-066). Owns `agent_runs` and `screening_results` (ADR-103). PROTECTED.

## Public interface (`api.py`)
- `AGENTS`, `spec(agent_id)`: specs from `specs/*.yaml`, rendered into `specs/_specs.py` by `abacus_tools.codegen.agent_specs` (drift: `--check`):
  - validated at import;
  - a spec's prompt must be registered;
  - its task scope may hold only actions the matrix gives agents as `task_scope`.
  - it declares `work_class` (its queue, ADR-071; the screener is `time_sensitive`), `essential` (ADR-069 as named by ADR-105) and `cheaper_tiers` (each strictly cheaper than `tier`; empty until one passes its evaluation suite).
- Screening starts only through `kernel.dispatch` (`screenings.py`, which registers `WORKFLOWS`), on the screener's class queue. After `create_run` it holds a work slot (`screening.acquire_slot`, behind `patched("work-slots")`): a waiting run stays `running` with `queued_reason` and `estimated_start_at` (audited `agent_run.queued` / `agent_run.resumed` on change; no API exposes agent runs yet), and past the class's maximum wait it fails `capacity_timeout`.
- **Admission (018c):** a screen the gateway doesn't admit marks the run queued (`provider_capacity` or `deferred`, with an estimate) and raises `NotAdmitted` to the workflow. Behind `patched("admission")`, the workflow sleeps (`retry_after`, jittered, at most 60 s) and screens again, until the class's maximum wait gives `capacity_timeout`. The run keeps its slot while it waits (F1). The reason is cleared only once a screen is admitted, so repeated refusals write no audit events. Asks back off from 5 s to 60 s. The class's maximum wait covers the slot and admission waits together. A call too large ever to fit fails at once (`context_too_large`).
- `create_screening_run(tenant_id, evidence_version_id, source_event_id, requested_by) -> run_id | None`:
  - one run per agent and event;
  - the initiator is `requested_by` from `evidence_version.created`: the person a retrieval ran for (retrievals only for now; uploads don't pass it yet);
  - with no initiator, an initiator without an active membership, or no ledger snapshot behind the version, there is no run.
- `load_agent_context(tenant_id, run_id) -> AgentContext`:
  - proven from the running run row and the initiator's live membership (resolved inside identity);
  - its task scope is the run's intersected with the current spec's;
  - a run from another spec version is failed.
  - Workers call it first.
- `fail_run(tenant_id, run_id, code)`: ends a running run as failed (`agent_run.failed`). Idempotent.
- `screen(agent) -> ScreeningOutcome`:
  - builds the context from totals, cell positions and untrusted account names, all computed by code from the evidence spreadsheet. The sheet must match the rendered layout exactly (`SheetLayoutError` otherwise), so a client line can't pose as the Total row;
  - calls the gateway with `ScreeningOutput`;
  - verifies every citation against the stored spreadsheet;
  - records a `screening_results` proposal and completes the run;
  - code forces `needs_revision` when a citation fails or the figures don't add up;
  - terminal errors fail the run; `ProviderError` leaves it running for a retry.
  - Output still invalid after one repair escalates the run with no result.
- `Handoff`, `ScreeningOutput`, `Citation`, `VerifiedCitation`, `verify_citations`; `install_fake_responses(FakeModel)` and `screening_responder` (local and test only).
- `router`: `GET /v1/engagements/{id}/screening-results` (`evidence.read`).
  - Returns the latest result per evidence version, through `visible()`.
  - Read-only: nothing acts on a proposal.
  - `rationale`, `quote` and `unverified` are model text, which the SPA renders only through `AgentText` (ADR-065).
  - `screening_results_for(ctx, engagement_id)` is the service behind it.
- `run_outcome(tenant_id, run_id)`: what a run recorded (status, failure code, screening result).

## The engagement agent v1 (SPEC-027; TASK-050)
Deterministic policies, no model: the platform retrieves and suggests by rule; agents screen and propose.
- **Workflow:** `EngagementAgent` (`engagement_agent_workflow.py`), one per engagement (`engagement-agent:<tenant>:<engagement>`), on the background class. Events arrive as `event` signals through `kernel.dispatch.signal_with_start`. Each runs `engagement_agent.handle`, which reads the current state and applies one policy. A failing event is skipped. It continues as new every 500 events (or when Temporal suggests it), and ends when the engagement is archived. Replay histories: `tests/workflows/histories/engagement-agent-v1-*.json` (`abacus_tools.workflows.record_engagement_agent`).
- **Routing:** with `engagement_agent.enabled` on for the firm, the relay sends `engagement.created`, `evidence_version.created`, `connection.created`, `request_item.classified` and `inbox_file.added` to the engagement's agent, and the direct handlers (screening, automatic retrieval) step aside. `firm.agents_resumed` signals every open engagement's agent. Off, nothing changes.
- **Policies** (`engagement_agent.py`): every policy checks the firm pause, the engagement pause, archived and the flag before its own rule, and writes one feed row per event.
  - P-0: started, paused, resumed. A resume screens what was skipped while paused since the last resume (with its original initiator), and runs the retrieval rule once.
  - P-1: screen new evidence (same workflow ID and initiator as before; not at Advise).
  - P-2: the platform's retrieval rule, started through engagements (`run_auto_retrieval`, registered by connections, which nothing imports), recording why it didn't run.
  - P-3: records how many items the matching rule suggested for a waiting inbox file; never assigns.
- **Feed and switches:** `agent_activity` (insert-only, references only). `GET /v1/engagements/{id}/agent` and `/activity` (`activity.read`); `POST …/agent/pause` and `/resume` (`agent.pause`: partner, manager). The firm switch is identity's (`/v1/firm/agents/pause`, `firm_agents.pause`, fresh MFA).
- In TASK-050 the agent starts work that already runs under a person; its own `AgentContext` under the partner arrives with reminders (TASK-051).

## Engagement agent v1, part 2 (SPEC-027; TASK-051)
- **The daily tick** (workflow v2, `patched("daily-tick")`): the agent waits for an event or 09:00 on the next business day in the firm's time zone (`engagement_agent.next_tick`, recorded). The tick runs P-2's daily retrieval, P-4 and P-5. Replay histories `engagement-agent-v2-*.json` sit beside v1's.
- **Its own authority:** `engagement.agent` is a `PolicySpec` (no prompt, tier, schema or evaluation suite; `spec.declared`). Each sending tick gets an `agent_runs` row with the engagement's earliest active partner as initiator. With no active partner the agent pauses itself (`self_paused_reason: no_partner`) and resumes when there's one.
- **P-4 reminders** (`reminders.py`):
  - items past their due date and still open or sent back are reminded on the first business-day tick after it, then every 3 business days, at most 3 per due date; a changed due date starts again;
  - one email per contact per tick: the assignee, else the client admins;
  - Routine sends as the agent through `communications.send_reminder` (recorded first as a draft, so a failed send waits for a person instead of being emailed again); Advise drafts (`reminders.drafted`);
  - nothing client-facing before the engagement is open.
- **P-5 digest:** `agent.digest` (in the app) with the overdue count in the feed.
- **Drafts:** `GET /v1/engagements/{id}/reminders` (`follow_up.draft`); `POST …/reminders/{id}/send` (optional note) and `/dismiss` (`follow_up.send`).
- **Starting every agent:** `python -m abacus_tools.engagement_agents start <tenant-id>` (idempotent).

## Temporal (TASK-011b)
- `SUBSCRIPTIONS`: `evidence_version.created` → `start_screening`, which starts `screening:<tenant_id>:<evidence_version_id>` (tenant-qualified: the Temporal namespace is shared).
  - The worker's outbox relay delivers each event at least once. A redelivery attaches to the running workflow or finds it finished; a failed workflow may be started again.
  - `requested_by` is taken only from the relayed event.
- `ScreeningWorkflow` (name `screening`) runs these activities:
  1. `screening.create_run`: no run (`None`) ends the workflow as `skipped`;
  2. `screening.screen`: one activity, 5-minute timeout with a 30-second heartbeat (a timed-out attempt is cancelled before its retry), up to 4 attempts; `create_run` and `fail_run` have 2-minute timeouts;
  3. on any failure, cancellation included, `screening.fail_run`, which retries until it succeeds.

  It returns `ScreeningOutcome(status, run_id, code, screening_result_id)`.
- **Activities** prove the agent's context from the run row:
  - errors cross to Temporal as class names only;
  - terminal errors are non-retryable (`screen` has already failed the run); provider outages and infrastructure errors are retried;
  - a run that has already ended reports what it recorded;
  - an initiator who has lost their membership ends the run as `initiator_inactive`.
- **Spec limits:** `max_seconds` bounds each model call (a timeout is a `ProviderError`); a `single_call` agent has `max_steps: 1`; `output_schema` must be `ScreeningOutput`, the model the gateway validates against.
- **Replay (AC-19, ADR-090):** `tests/workflows/histories/screening-v<N>-{completed,skipped,provider-unavailable}.json` are recorded with `python -m abacus_tools.workflows.record_screening`, decoded and scrubbed.
  - Never overwrite one: a changed workflow uses `workflow.patched(...)` and adds `v<N+1>`.
  - Every version must keep replaying.
- **Evals:** `make evals` runs `evals/screening/` through the real pipeline and gateway (`FakeModel` today) and writes the cost per case to `backend/.evals/screening.json`.

## Rules
- **Agents propose; humans decide.**
  - Screening never changes a request item's status.
  - Actions with `agent: deny` are authorised only for an `AuthContext` parameter (AGENT-001).
- **An agent never exceeds its initiator.** `authorise` intersects the agent role, the run's task scope and the initiator's live rights. For agent-only actions (`screening.run`), the initiator must be allowed `evidence.read`.
- **Code computes, models judge.** No rows of amounts reach the model, only totals and positions. Screening checks the sheet against itself, not against the ledger.
- **Every model call goes through `ai_gateway`** with the spec's prompt, tier, budget and limits.
- **Dependencies:** identity, engagements, organisations, evidence and requests (BOUND-002).
- **Review proposals (TASK-019; ADR-106):** at import, `api.py` registers `proposals_for` (the latest proposal per version, read like the board's screening results and audited) and `proposal_of` (one version's latest, in the caller's transaction) with evidence (`register_proposal_source`). Agents never decide (REVIEW-001).

## The engagement graph (SPEC-008; TASK-023 D1)
`engagement_graph(ctx, engagement_id)` (`GET /v1/engagements/{id}/graph`, `engagement.read`) is built on read, by code, from the owning modules' APIs. It returns:
- the engagement and its team;
- the pinned methodology version;
- each audit area with its request items (status, tier, latest evidence version and screening action) and its accounts in the latest ledger snapshot, mapped by the version's rules;
- the coverage gaps.

Agents will read the same view as context.

## Knowledge (SPEC-009; TASK-024)
The firm's methodology documents, recalled by vector search. Knowledge is firm-wide in v1, and every read and write is checked on the firm.

**Adding a document:** `POST /v1/knowledge/documents` (`knowledge.manage`, fresh MFA) takes plain text or Markdown. The document is stored as `pending` with deterministic chunks (`knowledge_chunks.py`), and `knowledge_document.added` is emitted.

**Embedding:** `KnowledgeEmbeddingWorkflow` (batch class) then embeds the chunks in batches of 64 through `ai_gateway.embed`:
- the document becomes `ready` when every chunk has a vector;
- it becomes `failed` (with a fixed code) on a budget refusal or a provider that stays down.

**Withdrawing:** `POST …/{id}/withdraw` excludes the document from search immediately.

**Searching:** `POST /v1/knowledge/search` (`knowledge.read`) is exact cosine over the caller's firm's `ready` chunks that were embedded with the current model, with the tenant filter explicit as well as under RLS. There is no ANN index, so no index is shared across tenants (Q1, ADR-053).

**For agents:** `search_knowledge` and `knowledge_context` wrap hits as untrusted, delimited `internal` context (ADR-052).

## Autonomy and "Screen now" (SPEC-024; TASK-042)
- **At Advise:** `start_screening` does nothing when the firm is at Advise (logged `screening.skipped`).
- **"Screen now":** `request_screening(ctx, engagement, version)` is `POST …/screening-results/request` (`screening.request`: engagement partner, manager, senior, staff; 202).
  - It dispatches the same workflow with the same ID, so a running or finished screening is attached to, not repeated.
  - The requester is who the agent acts for. Audited `screening.requested`.
