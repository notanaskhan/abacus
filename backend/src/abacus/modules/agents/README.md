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
