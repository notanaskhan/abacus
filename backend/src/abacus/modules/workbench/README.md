# workbench

Zone: amber (the session workflow and turn activity are red). Pre-registered by F-03-T08 (ADR-140).

Built: P-10-T04 tables (0682); P-10-T43 sessions core: `sessions.py` (snapshot with DEC-87
visibility, message post, `open_session`), `session_queue.py` (the side queue),
`session_workflow.py` (`WorkbenchSessionWorkflow`), `session_activities.py` (one turn). Turns are
runs: `agents.api.open_turn_run`, `run_session_turn`, `open_plan_child_run` (DEC-4301).

Will own (docs/plan/03-backend-architecture.md §2.2): Agent definitions and versions, installs, schedules, triggers, workbench sessions and items, saved prompts.
