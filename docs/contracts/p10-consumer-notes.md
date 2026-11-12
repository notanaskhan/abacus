# P-10 runtime v2: consumer notes (P-10-T55)

For the epics that build on the agent runtime v2 (SPEC-647; ADR-233, ADR-234, ADR-232). Each note
says what P-10 gives, how to use it and what stays the consumer's. How-to:
`docs/architecture/reference/ai-agent.md` ("Runtime v2"). Contracts: C6 v2
(`docs/contracts/agent-runs.md`, frozen), C17 (`docs/contracts/tool-registry.md`, v1 frozen).

## P-09 (the dock, the trace, the run engine)
- C6 v2 is frozen: run view, items feed (`items?after_seq=`), trace and trace export keep P-09's
  ownership; P-10 owns the run commands (`/v1/agent-runs/{id}/plan/approve|edit|cancel`,
  `questions/{qid}/answer|skip`, `messages`, `steps/{sid}/retry`) and the streams.
- `SseRunSource` (`apps/web/src/domain/agents`) feeds the same `RunStore` as `PollingRunSource`
  behind `realtime.sse`; events are identifier-only, each followed by a REST fetch. The polling
  source stays the fallback (RB-28).
- v2 durable-record fields are in the JSON trace export and the signed manifest; the PDF export's
  v2 fields are cut-list item 3 (A-07 or G-02 depth).
- Plans and proposals are now C13 human gates (`agent_run_plan`, `run_proposal`; DEC-4401): the
  home "waiting on you" counts include them.

## T-04 (tax tools, TAX-08 assistant, return analyst and drafter)
- Tax tools register through C17 in `modules/tax/tools.py` with `@agent_tool` (the module's
  `api.py` imports them). Kinds: read and compute freely; propose through `create_proposal`;
  never `approved_write` without a grant.
- `tax.return_analyst` modes (K-1 treatments, residency) and `tax.account_mapper` are v2 specs;
  `client_data` stays `none` until a signed Bedrock report clears it (DEC-4411; the evaluation
  account's step). G-5 to G-7 per firm and taxpayer still apply.
- Proposal targets `return_field` and `tax_account_mapping` are registered by tax; applying them is
  tax's adapter, on a person's approval.

## W-02 (the workbench: WB-01/02/03, session list, context picker, `workbench.assistant`)
- The sessions core is built (`modules/workbench`): `open_session`, message post, the side queue,
  `WorkbenchSessionWorkflow`; each turn is a run (`agents.api.open_turn_run`); a turn that
  proposes opens a child run that waits for plan approval.
- The screen kit is F-07's T4 chat kit (`packages/ui/src/agent/chat`: `WorkbenchLayout`,
  `SessionList`, `ChatHeader`, `ChatThread`), with fixtures in
  `apps/web/src/fixtures/seed/tpl04-sessions.ts`.
- Not built for W-02: the `session:` realtime topic (reserved, unregistered), the
  `workbench.assistant` capability and its evals, the context picker. J11 b2-b3 stay `test.fixme`
  until WB-01 g lands (P-10-T50).

## I-02 (`briefing.today`)
- Runs on the runtime as a v2 spec (P-10 expects read tools only, no proposals). Register its read tools in
  the modules that own the data (C17), never in `agents`. Schedules arrive with W-03
  (`kernel.dispatch.schedule`); until then the brief is started by a person.

## K-03 (agent columns in batch mode, the estimator, presence)
- P-10 expects batch mode as many runs, one per row, each a normal `AgentRunWorkflow` on the background work
  class; budgets and admission (ADR-069, ADR-071) apply per run.
- P-10 reserves the `presence:{object_ref}` topic kind; K-03 registers it
  (`kernel.realtime.register_topic`) with its own authorizer.

## K-04 (engagement triggers P-8, review package, set up with AI)
- The engagement run (`POST /v1/engagements/{id}/runs`) plans from methodology in code; a
  section's work is a `run_step.<kind>` its owning module registers with
  `agents.api.register_run_step(kind, handler)` (the workpapers module's `workpaper` is the model).
- P-10 did not touch the live `EngagementAgent` inside the freeze; P-8 triggers starting v2 runs
  are K-04's, behind its own flag, after the M17 flip (`docs/runbooks/runtime-v2-flip.md`).

## A-07 (archive packaging, AUD-25)
- `agents.api.adopted_run_traces(tenant, engagement_id)` answers each adopted run's newest frozen
  content trace (run id, number, version, body hash) for the binder (AC-RR5).
- Durable run records are kept for the longer of 7 years and the engagement's retention, under
  legal holds and in the hash chain; `run_events` prune at 30 days, `realtime_events` at 24 hours.
