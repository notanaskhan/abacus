# workbench

Zone: amber (the session workflow and turn activity are red). Pre-registered by F-03-T08 (ADR-140).

Built: P-10-T04 tables (0682); P-10-T43 sessions core: `sessions.py` (snapshot with DEC-87
visibility, message post, `open_session`), `session_queue.py` (the side queue),
`session_workflow.py` (`WorkbenchSessionWorkflow`), `session_activities.py` (one turn). Turns are
runs: `agents.api.open_turn_run`, `run_session_turn`, `open_plan_child_run` (DEC-4301).

## How a session works (P-10-T55)
- A person opens a session (`open_session`) and posts messages; each message becomes a **turn run**
  on the agents runtime (`agents.api.open_turn_run`), so a turn has a plan, steps, tools, questions
  and proposals like any v2 run, and the run's records and trace.
- `WorkbenchSessionWorkflow` (id `session:<tenant>:<session>`, started and signalled only through
  `kernel.dispatch.signal_with_start`) takes one turn at a time from the side queue
  (`session_queue.py`): a message typed while a question is open is answered first and the
  question stays open. A turn is one activity, the run's read-only harness turn. A turn that
  proposes writes writes one child run (`open_plan_child_run`) and starts its `AgentRunWorkflow`,
  which waits in `awaiting_plan_approval` for a person; the agent never decides it.
- The workflow ends after an hour idle (the next post starts it again) and keeps its history short
  with continue-as-new; replay histories are `session-v1-*.json`.
- The thread's items are the run items (C6 v2); the screen side is the T4 chat kit
  (`packages/ui/src/agent/chat`, F-07: `WorkbenchLayout`, `SessionList`, `ChatHeader`,
  `ChatThread`). Agent text only through `AgentText`/`AgentBlocks`; a locked session shows no
  figure (INV-3).
- Visibility is DEC-87's: a session is its owner's, plus whoever the owner shares it with;
  attribution reads "‹person› via Agent".
- Real time: a session's items reach its thread on the `session:<id>` topic of `GET /v1/events`
  (`session_events.py`, TASK-7325); the turn's runs reach the dock on `run:<id>`.

Will own (docs/plan/03-backend-architecture.md §2.2): Agent definitions and versions, installs, schedules, triggers, workbench sessions and items, saved prompts.
