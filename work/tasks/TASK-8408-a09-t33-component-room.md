---
id: TASK-8408
title: "A-09-T33: POR-23 portal read model and routes"
spec: SPEC-658
acceptance_criteria: [AC-7]
risk_zone: amber
status: in-review
branch: a09-t33-component-room
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T33
---

## Objective
Spec section: docs/plan/epics/A-09.md §3.7 (POR-23). Portal read model and routes: the room with the two-line header and n of 4, instructions and PDF, acknowledge, deliverables in client words, uploads and drops with provenance component_auditor_upload and the ambiguity picker, questions on component_thread; scope_only everywhere; no firm-only words or agent attribution.

## Plan (amber)
1. `assurance/component_room.py`: the room only for a live client person with an active `component_auditor` grant on the component (`scope_only`, else 404); the allowlist `ROOM_FIELDS`; group and component names and the firm's own name; deliverables in client words (`client_word`); instructions as sent and the C11 final PDF (409 `letter_rendering` until filed); acknowledge through `component_auditors.acknowledge`; upload (a new evidence version, `component_auditor_upload`, channel portal) linked to this room's deliverable only (404 for another), or None for the picker on a drop; Questions on `component_thread` through collaboration's client threads.
2. `evidence.file_component_upload` (scanned before stored; source documents of the group engagement).
3. `portal/component_room_contract.py`: all eight routes implemented; uploads take the raw body with `?filename=` like the respondent page.
4. Tests: `tests/unit/assurance/test_a09t33_component_room.py` (allowlist, client words).

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5407). Lint and pyright clean; the app imports. Partial: a drop's file is kept without a deliverable until the picker links it (no link-after route yet); the PDF is served from the render's evidence version without a C10 publish; integration tests for scope isolation (another component 404) run at the end pass. Gates and tests run once at the S48 end pass (build first, test last).
