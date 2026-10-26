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
- **P-4 follow-ups** (`follow_ups.py`; renamed from reminders by F-03-T16):
  - items past their due date and still open or sent back are reminded on the first business-day tick after it, then every 3 business days, at most 3 per due date; a changed due date starts again;
  - one email per contact per tick: the assignee, else the client admins;
  - the agent only drafts, at every autonomy level (TASK-104; DEC-74, P-06-T14): a person reads the draft and sends it. The tick runs as an activity of `EngagementAgent`, which holds no business state, so the change needed no `workflow.patched` marker and the recorded histories replay unchanged (DEC-220). `draft_now` drafts for everything overdue on a person's request;
  - nothing client-facing before the engagement is open.
- **P-5 digest:** `agent.digest` (in the app) with the overdue count in the feed.
- **Drafts:** `GET /v1/engagements/{id}/follow-ups` (`follow_up.draft`); `POST …/follow-ups/{id}/send` (optional note) and `/dismiss` (`follow_up.send`). Since P-06-T14 these SPEC-027 routes send through the same approval-grant hold as follow-ups v2 (`send_overdue`).
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

## The upload reviewer (SPEC-030; TASK-058)
- **Spec** `specs/evidence.upload_reviewer.yaml`: prompt `evidence.upload_review@v1`, small tier, $0.02 and 60 s a review, `propose` only, scope `evidence.read` + `upload_review.run`, `document` the one untrusted input; a low-confidence flag routes to `hidden`.
- **Run** (`upload_review.py`): `create_review_run` (an extracted evidence version, a person to act for, the daily cap) and `review` (context by code: engagement facts, the request and its kind, SPEC-029's client checks, then the document excerpt from `evidence.review_material`; the gateway enforces the data boundary; `DataBoundaryRefused` fails the run as `data_boundary`).
- **Quotes** (`document_citations.py`): verified against the extraction's page text or cell, after NFKC, case and whitespace normalisation and dropping invisible formatting characters. A flag is shown only with a verified quote and confidence at or above 0.5.
- **Results:** `upload_reviews` and `upload_review_flags` (insert-only). Nothing triggers a review in the product yet (TASK-059); the evaluation runs it (`python -m abacus_tools.evals --agent evidence.upload_reviewer --route direct`, real routes only).
- **In the product (TASK-059):** evidence emits `upload_checks.recorded`; the engagement agent's **P-6** (or `review_start.start_upload_review` with the agent off) starts `UploadReviewWorkflow` (`upload_review:<tenant>:<version>`, background, work slot, waits when not admitted) at Routine or above with `upload_review.enabled`, for the engagement partner. Without a real model route (the local stack) nothing starts: the feed records `no_real_model`, and "Review now" (`POST …/evidence-versions/{v}/review`, `upload_review.request`) answers 409 `ai_review_unavailable`. Reads (`GET …/review`, `GET …/review-flags`, `upload_review.read`, firm roles only) return shown flags with verified quotes only. An `altered` flag is hidden when code already found a balance, totals, period or company problem.

## The matcher (SPEC-033; TASK-065)
- **Spec** `evidence.matcher` v1 (`specs/evidence.matcher.yaml`): prompt `evidence.inbox_match@v1`, small tier, propose only, $0.01 per file, proposals below 0.5 confidence kept hidden, suite `evals/matching`.
- **`inbox_match.py`:** `create_match_run(tenant, inbox_file, event, person)` (a real route, an extraction and candidates; the daily cap) and `match(agent, inbox_file)`. The context gives candidates as `R1`–`Rn` (D1) with code's scores and reasons, and the document excerpt as the only untrusted field. Code maps references back (unknown or repeated ones are discarded), verifies quotes (`document_citations`) and records `inbox_match_runs` and `inbox_match_proposals` (insert-only). A non-synthetic firm ends as `data_boundary`.
- No trigger or screen yet (TASK-066). Measured by `python -m abacus_tools.evals --agent evidence.matcher --route direct`; reports in `docs/operations/matching/`.
- **In the product (TASK-066):** evidence emits `inbox_file.extracted`; the engagement agent's **P-7** (or `match_start.start_match` with the agent off) starts `InboxMatchWorkflow` (`inbox_match:<tenant>:<file>`, background; activities `inbox_match.create_run` and `inbox_match.match`, reusing the screener's slot and fail steps) for the engagement partner when `matching.enabled` is on, a real route exists, the firm is at Routine or above, and code wasn't decisive (`evidence.worth_matching`; decisive files record nothing, D3). Skips record `matching_off`, `no_real_model`, `advise`, `no_partner` or the pause. "Suggest with AI": `POST …/inbox/{file}/match` (`inbox_match.request`; 409 `ai_match_unavailable` without a real route). Firm reads: `GET …/inbox-matches` (`inbox_match.read`, firm roles): each file's latest run, its shown proposals and verified quotes. `agent_runs.inbox_file_id` (0050) ties runs to files. `match_start.picks_for` is registered into evidence (D1): the inbox listing puts the matcher's picks first as `source: matcher`, request IDs only.

## The guidance drafter (SPEC-035; TASK-072)
- **Spec** `requests.guidance_drafter` v2 (TASK-074 added `methodology.read`): prompt `requests.guidance_draft@v1`, small tier, propose only, $0.005 per item, untrusted inputs `item` and `examples`, suite `evals/guidance_drafting`.
- **`guidance_draft.py`:** `create_draft_run(tenant, engagement, item, event, person)` and `draft(agent, item)`. Context: the year end, the item (description, area, document kind, tier) and up to three of the firm's own guidance texts as tone examples, both untrusted. Records `guidance_drafts` (insert-only) with `passed_checks` and the reason codes.
- **`guidance_checks.py`:** form checks by code: length; no link, email, phone, amount, date or year (any year: guidance is copied on roll-forward); no model talk or instruction to the auditor; not a copy of the description; no capitalised name absent from the input. A failing draft is never shown.
- Nothing is applied and no screen exists yet (TASK-073). Measured by `python -m abacus_tools.evals --agent requests.guidance_drafter --route direct`; the rubric judge (`eval.guidance_judge@v1`) is informational until calibrated against the founder's labels (`docs/operations/guidance-drafting/labels-to-score.csv`).
- **In the product (TASK-073, `draft_start.py`):** "Draft guidance" (`POST …/request-items/draft-guidance`, `guidance_draft.request`, flag `guidance.drafting`, a real route; 409 `ai_drafting_unavailable` otherwise) starts one `GuidanceDraftWorkflow` per item (`guidance_draft:<tenant>:<item>:<event>`, batch; activities `guidance_draft.create_run` and `guidance_draft.draft`, reusing the screener's slot and fail steps). `GET …/guidance-drafts` (`guidance_draft.read`, firm roles): pending drafts that passed the checks. `POST …/guidance-drafts/approve` and `/discard` (`guidance_draft.decide`): edits are checked again; several at once need `confirmed_read`; each draft gets a `guidance_draft_decisions` row (insert-only) and approval writes the item through `requests.apply_drafted_guidance` (source `drafted`) in the same unit of work.
- **On templates (TASK-074):** a firm-level run (`agent_runs.engagement_id` null, `methodology_version_id` set; a CHECK allows only the drafter). Its `AgentContext` has no engagement: it relates to the firm only (`agent.engagement` raises `Forbidden`), its initiator must hold `methodology.read`, and it costs the firm's month and daily cap. `create_template_draft_run(tenant, version, position, event, person)` and `draft_template(agent, position)`: context without a year end, the template's own guidance as examples; records `template_guidance_drafts`. Routes under `/v1/methodology/versions/{id}`: `POST draft-guidance` (202, `template_guidance.request`), `GET guidance-drafts` (`template_guidance.read`), `POST guidance-drafts/approve` and `/discard` (`template_guidance.decide`; `template_guidance_decisions` keeps the final text), `POST publish-drafted` (`methodology.manage`, fresh MFA): the template's next version via `engagements.publish_drafted_version`, latest version only (409 `version_not_latest`, `nothing_to_publish`).

## Stages for real firms (SPEC-036; TASK-076)
- **`stages.py`:** a cleared agent is `shadow` for a real firm until the newest `agent_stages` row says otherwise (`live`, `off`). Runs record `agent_runs.shadow` when they start (`starts_in_shadow`); every firm-facing reader leaves their output out (`_shown_run`), so promotion shows only later runs. Synthetic firms never run in shadow.
- **Stages change only through the founder's command,** through the owner role, audited (`agent_stage.changed`): `python -m abacus_tools.agent_stage report <firm> <agent>` and `set <firm> <agent> <shadow|live|off> "<note>"`. `live` is refused under 50 shadow runs over 14 days; the report compares the screener's shadow proposals with people's decisions.
- `assistants(tenant)` gives identity's disclosure the cleared agents and their stage.

## The entry assessor (SPEC-037 Q4; TASK-085)
- **Spec** `fieldwork.entry_assessor` v2: prompt `fieldwork.entry_assess@v2`, small tier, propose only, $0.02 per entry, untrusted inputs `entry` and `documents`, batch, `client_data: none`, suite `evals/entry_assessment`.
- **`entry_assess.py`:** reads one selected entry (`fieldwork.api.entry_facts`) and up to three documents a person tied to it: evidence linked on its newest result, then what fulfilled its support requests (D1; never a search). `ask` makes the one gateway call; `check` verifies every citation against the extraction (`document_citations.verify`) and, for amount claims, whether the quote holds the entry's amount (`shows_amount`, ADR-050). `explained` is shown only with all citations verified, a party citation and a matching amount quote; otherwise `unclear`. Records `entry_assessments` (insert-only; shadow runs hidden).
- **`assess_start.py`:** `POST …/procedures/{id}/assess` (202, `entry_assessment.request`, flag `fieldwork.assessor`) starts one `EntryAssessWorkflow` per entry with documents and no assessment yet; `GET …/procedures/{id}/assessments` (`procedure.read`). Nothing is pre-filled into results (ADR-005); assessments stay out of the workpaper (D2).

## The screening aggregate (P-06-T20; DEC-48, DEC-324)
- **What:** the SHL-20 card for one request batch. It is a `request_batch` row of `screening_results` (migration 0154), composed by code in a system context (`screening_aggregate.compose_for_item`).
- **Inputs:** the item's live fulfilments, minus withdrawn versions. For each file:
  - code's facts (`evidence.api.screening_facts`: the document's dates and the `wrong_period` check);
  - its newest completed upload review's shown flags.
- **Checks:**
  - "Right document" (model): a shown, code-verified `irrelevant` flag.
  - "Right period" (code only): the request's `period_start/end` against the document's dates.
- **Verdict:** any flag makes it flagged; both checks passing make it passed; anything else is not screened.
- **Chain:** each change inserts a row that supersedes the previous one (`batch_no + 1`). An unchanged composition writes nothing. The database refuses an aggregate from an agent or a person.
- **Triggers:** `upload_checks.recorded`, `upload_review.recorded` (emitted with each review) and `evidence_version.withdrawn`.
- **Routes** (`screening_contract.py` over `screening_card.py`, behind `screening.card`):
  - `GET …/request-items/{id}/screening` (`upload_review.read`);
  - `POST …/screening/rerun` (`screening.request`). Reviews start only with `upload_review.request` and `upload_review.enabled`. Source events are deterministic. It is rate-limited to one rerun per item per 60 s under an advisory lock, and answers 409 `screening_running`;
  - `POST /v1/screenings/{id}/feedback` (`screening.feedback`; insert-only `screening_feedback`, sealed note).
  - None of these writes a request status or a review decision.
- **TRI fail-closed:** on a `tax_return` work item at a firm that is not synthetic:
  - `tri_gate.py` stops the reviewer's run and keeps model output out of the aggregate;
  - the gateway refuses every agent's call (`tax_return_information`).
  - Both hold until C19 registers §7216 consent.

## Follow-ups v2: drafted by the platform, sent by a person (P-06-T14; C5 v1.2 §12; DEC-74, DEC-220)
`follow_up_drafts.py` (PROTECTED) over `follow_up_routes.py`, behind `binders.engine`.
- **Draft** (`POST /v1/follow-ups/drafts`, `follow_up.draft`): over binders or requests, one follow-up per client contact per engagement from the firm's published Reminder template (C16, in the database; 409 `follow_up_template_missing` until imported), listing each open client-visible request once and never one already waiting in a draft to that contact. What is open comes from `requests.api` (`follow_up_reads.py`). The composition is the Request Chaser's (`drafted_by_kind = 'agent'`, the C-31 marker); the person who asked is the audit actor.
- **Edit** (`PATCH /v1/follow-ups/{id}`): a person's edit, sealed with `edit_fingerprint`; a sent one answers 409 `follow_up_already_sent`.
- **Send** (`POST /v1/follow-ups/{id}/send` or `/v1/follow-ups/send`, `follow_up.send`, `Idempotency-Key`): human only (the matrix denies the agent; `follow_up.sent` is in the database's human-only register), every client- or person-written value scope-checked at draft and again at send (409 `out_of_scope`, nothing written), held by an approval grant until the 10-s Undo window ends (ADR-161). The body sent is frozen in `body_sealed`; the relay's delivery of `follow_up.sent` sends the email through communications. Undo within the window voids the grant and puts the draft back; dismiss closes it.
- **Screening return** (SHL-20 b; TASK-1252, DEC-368): `POST …/request-items/{id}/follow-ups` drafts one return from the firm's Return template with the files it returns. Its send records one `send_back` per file and moves the request to Returned in the grant's unit of work; its delivery, after the window, posts the shared comment with the email. It is sent alone (409 `follow_up_send_alone` in a bulk send); Undo also undoes the send-backs.
- No model text reaches a client (DEC-79, ADR-111).

## Withdrawn versions (P-06-T19; ADR-162 §4)
Agents read `evidence.api.withdrawn_among` / `is_version_withdrawn` and leave a client's withdrawn upload out: the upload reviewer's runs record nothing for it, and the screening card, the screening aggregate, the engagement graph, the run trace, run records and the gate facts skip it.
