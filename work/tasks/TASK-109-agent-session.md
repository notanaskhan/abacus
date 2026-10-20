---
id: TASK-109
title: "SPEC-044: the agent procedure session — plan approval starting selection, gate cards, the agent's row assessments, and a preparer adopting them"
spec: SPEC-044
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6]
risk_zone: red
status: done
branch: spec-044-agent-session
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
- Migration 0065.
- `fieldwork/session.py` (plan, approve plan).
- `fieldwork.api.record_result` with adoption.
- `agents/adopt.py` and route.
- Matrix `entry_assessment.adopt`.
- Web: `AgentSession.tsx` panel per procedure.

Approved by founder (2026-10-20, "proceed with item 4").

## Done
- Migration 0065 (`procedure_session_events`; `item_results.adopted_assessment_id`).
- `fieldwork/session.py`: plans by definition (code's words) and `approve_plan`, which starts the selection when there's none.
- `fieldwork.api`: `record_result` takes `adopted_assessment_id`; `items_with_results`. `ItemOut.adopted`.
- `agents/adopt.py` and `POST /procedures/{id}/adopt` (`entry_assessment.adopt`): explained → supported; not explained → exception with the agent's reason; unclear left alone; rows with a result skipped.
- Web: `AgentSession.tsx` in each procedure section.
  - A conversation of code-worded agent messages: plan with **Proceed with plan**, selection, sample (approved in the Selection pane), one request (**Send the request**, with a ten-second Undo), **Read the support**, **Adopt n results**, triage with rows prepared and reviewed.
  - A clear message when the assessor isn't available.

## Definition of done
- [x] `test_adopt.py` (3), `spec044session.test.tsx` (2); the fieldwork, flow and notes screen tests pass; `make check-fast` passes.
- [x] Checked live: plan approval recorded; the gates in order; "Read the support" says the agent isn't available on a stack with no model (409 `ai_assessor_unavailable`).
- [ ] The agent's reading not walked live with a real model (the dev stack runs the fake route).
