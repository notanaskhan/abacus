---
id: TASK-8406
title: "A-09-T27: Component auditors service"
spec: SPEC-658
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
branch: a09-t27-component-auditors
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T27
---

## Objective
Spec section: docs/plan/epics/A-09.md §3.6. Component auditors service in assurance: add auditor, evaluation facts, deterministic instructions draft from the firm's DB letter template with Needs-input rules, sections edit, C11 PDF, human send with approval grant and 10-second Undo issuing the component grant and POR-20 invitation, deliverables request, receive, review and return, milestones, make-reference card, acknowledge service, component_thread anchor.

## Plan (amber)
1. Migration `0944_component_instructions_send.py` on 0943: C11 family/kind `component_instructions`; `component_instruction_sends` (completed or undone once; undo only inside 10 s, CHECK).
2. `assurance/component_auditors.py`: auditors and evaluation; `template_sections` + `merge` (placeholders from code's facts: component PM, the group's CT, the milestones' dates; an unanswered placeholder is Needs input); draft and edit as insert-only versions; send (live person, complete, the auditor's contact, the version on screen) renders final through C11 with the send's approval, then `ComponentInstructionsSend` sleeps out the Undo and completes once (grant via `identity.grant_component_auditor`, invitation for a contact not yet signed in, Sent, `component_instructions.sent`); undo; acknowledge; deliverables (request + milestone, list with derived Late/Returned, review, return, receive); the EP's `make_reference` card and applier; `component_thread` anchor.
3. `group_contract.py`: the eleven component routes implemented; new `PATCH /v1/component-auditors/{id}/evaluation` and `POST /v1/component-instruction-sends/{id}/undo`; `ComponentInstructionsOut.send_id`. `reporting.contract` kind literal; `identity.contact_access.grant_component_auditor`; registry; error codes.
4. Tests: `tests/unit/assurance/test_a09t27_component_auditors.py`. Rollback: `alembic downgrade 0943`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5405). Lint and pyright clean; the app imports. Partial: the POR-20 `component_auditor_invitation` email is the invitation's own template (DB content via ADM-10 import, DF-40); the deliverable request email (`component_deliverable_request`) is not sent here (no template on main); no group risk assessment exists, so §5 always reads Needs input until a person writes it; the firm's letter template must be imported (Brightwater Hale's arrives with A-09-T30/G-04-T13 seed slices). Gates and tests run once at the S48 end pass (build first, test last).
