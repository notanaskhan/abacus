---
id: SPEC-318
title: "Agent transparency, first slice: the run list, the run trace and its JSON export over the runs that exist"
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-005, ADR-019, ADR-065, ADR-111]
related_specs: [SPEC-027, SPEC-036]
created: 2026-10-22
updated: 2026-10-22
---

## 1. Summary
This is P-09's first slice. It is read-only over the runs the agents already record.

- `GET /v1/engagements/{id}/agent-runs`: the run list.
- `GET /v1/agent-runs/{run_id}/trace`: the trace.
- `POST /v1/agent-runs/{run_id}/trace-exports`: the export.

Every figure on the trace is computed from rows that already exist:
- the run;
- the gateway's usage records for its attempts;
- its screening results;
- people's decisions on them.

Shadow runs are never shown (SPEC-036). Firm-level runs (no engagement) wait for a later slice. The model id is never shown; the trace names the runtime ("Abacus agent runtime"), the region and the no-training promise.

## 2. Acceptance criteria
- **AC-1 Run list.** The engagement's runs come newest first, through `visible()` on `agent_run.read`.
  - Who can read: the engagement team and firm leadership; independence is required.
  - Each run shows the agent's label, its state, when it started, who started it, what it worked on (a reference kind only), and its duration.
  - `state=active` keeps only unfinished runs.
- **AC-2 States.** The run status maps to the status words:
  - running → Running, or Queued while it waits for a slot;
  - completed → Finished;
  - escalated → Needs a person;
  - failed → Failed.

  Duration is computed from start and finish. No confidence figure is shown (I-12).
- **AC-3 Trace.** A timeline in time order:
  - the start, with who started it and whether a person or an event did;
  - the wait for a slot;
  - one row per gateway attempt, with its outcome code;
  - the output: the screener's proposal with its citation and unverified-claim counts, or for other agents, the counts of each list in the run's output;
  - each person's decision on it;
  - the finish, with its failure code.

  The summary gives the attempts and tokens. The run's own words come back as `model_text` and render only through AgentText (ADR-065). Records read: the subject and the task scope's size.
- **AC-4 Refusals.**
  - A shadow run, a firm-level run, or an unknown id answers 404.
  - A person off the engagement is refused by `authorise`.
  - The agent is denied `run_trace.export`.
- **AC-5 Screen.**
  - The Activity tab gains an "Agent runs" panel above the feed, with empty, loading, error and not-allowed states. When not allowed, the panel hides.
  - "Open trace" opens a 480px drawer showing the summary, the timeline, what it proposed, the agent's words and the records read.
- **AC-6 Export.**
  - Only the partner, manager or senior may export, and only after a recent sign-in (fresh MFA). Otherwise the screen offers "Confirm it's you".
  - The export is canonical JSON: sorted keys, UTC instants and rows in sequence, so the same trace gives the same bytes.
  - It carries a manifest: SHA-256, row count, renderer version and projection.
  - Each export is audited as `agent_run.trace_exported`, with the digest as a reference.
  - The browser downloads the file.

- **AC-7 The run and its writes (C6 v1; TASK-5000).**
  - `GET /v1/agent-runs/{id}` returns the run, a SHA-256 of its record and the caller's allowed actions.
  - `/trace/records-read` and `/trace/writes` return what the run read, and what it proposed with each newest decision. Writes are codes and references only.
  - The trace counts suggestions and proposals when the run recorded any.
  - The drawer has three views: Timeline, Records read, and Writes & approvals.
  - The runtime is named "Accrued Agent runtime" (DEC-87).

- **AC-8 Live feed (TASK-5001).**
  - `GET /v1/agent-runs/{id}/items?after_seq=` returns the header plus the new items: a tool card, the engagement agent's narration as code words, decisions, and any failure.
  - It answers `resync` when the client is ahead.
  - The drawer polls every 1.5 s while the run is active and the tab is visible. It shows "· live", narrates what the agent did, and stops polling when the run ends.
  - The run list refreshes while any run is active.

- **AC-9 Content and metadata (DEC-87, TASK-5002).**
  - Security and firm admins without an engagement role may open runs and traces as metadata: no model text, no record references, no narration.
  - The drawer says "You can see what ran, not the client content."
  - The engagement's people, and practice and quality oversight in scope, see the content (`run_content.read`).

- **AC-10 Agent dock, first slice (SHL-13; TASK-5003).**
  - The audit cockpit's Agent tab shows the engagement's runs as tool cards, oldest first: "Execute › ‹what it does›", the state, and the agent, time and initiator.
  - Expanding a card follows the run live and shows what it read, what it proposed, and what came after: narration, decisions, failure.
  - "Open trace" opens the WB-09 drawer.
  - The v1 activity list stays below the thread. A viewer refused `agent_run.read` sees only that list.
  - The dock decides nothing. Approve and decline wait for P-10's C6 v2 actions (P-09-T14).

## 3. Out of scope
- Live streaming, cancelling and retrying runs.
- Firm-wide run views.
- Per-step tool calls: legacy runs don't record them.
- PDF export.
