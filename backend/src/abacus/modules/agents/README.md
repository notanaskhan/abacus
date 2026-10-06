# agents

Agent specs, agent runs and screening (ADR-005, ADR-025, ADR-047, ADR-050, ADR-054, ADR-066). Owns `agent_runs` and `screening_results` (ADR-103). PROTECTED.

## Public interface (`api.py`)
- `AGENTS`, `spec(agent_id)`: specs from `specs/*.yaml`, rendered into `specs/_specs.py` by `abacus_tools.codegen.agent_specs` (drift: `--check`):
  - validated at import;
  - a spec's prompt must be registered;
  - its task scope may hold only actions the matrix gives agents as `task_scope`.
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
- `Handoff`, `ScreeningOutput`, `Citation`, `VerifiedCitation`, `verify_citations`; `install_fake_responses(FakeModel)` (local and test only).

## Rules
- **Agents propose; humans decide.**
  - Screening never changes a request item's status.
  - Actions with `agent: deny` are authorised only for an `AuthContext` parameter (AGENT-001).
- **An agent never exceeds its initiator.** `authorise` intersects the agent role, the run's task scope and the initiator's live rights. For agent-only actions (`screening.run`), the initiator must be allowed `evidence.read`.
- **Code computes, models judge.** No rows of amounts reach the model, only totals and positions. Screening checks the sheet against itself, not against the ledger.
- **Every model call goes through `ai_gateway`** with the spec's prompt, tier, budget and limits.
- **Dependencies:** identity, engagements, organisations, evidence and requests (BOUND-002).
