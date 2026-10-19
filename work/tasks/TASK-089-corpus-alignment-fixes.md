---
id: TASK-089
title: Alignment fixes after the planning corpus review — the EQR never signs a workpaper as reviewed, agents never sign off, agents are off for a real firm until set to shadow, and agent and sign-off copy
spec: SPEC-036
acceptance_criteria: [AC-5]
risk_zone: red
status: done
branch: task-089-alignment-fixes
worktree: spec005
created: 2026-10-19
updated: 2026-10-19
---

## Objective
Fix where built work conflicts with the planning corpus (`~/Downloads/abacus/{screens,epics,cross}`) on compliance and wording, before more is built on it.

## Scope
**In**
- `permission-matrix.yaml`:
  - `workpaper.sign_reviewed` drops `reviewer`. The EQR signs only at L5 (epic P-04 R-SO-3); the TASK-084 D3 decision is reversed.
  - `workpaper.sign_ready` drops `engagement_partner`, matching ADR-131 Q2 (staff, senior or manager prepare).
  - Both sign-off actions add `agent: deny` (INV-1).
- Agent stages:
  - With no `agent_stages` row, a cleared agent is `off` for a real firm (epic Q-02 AC-4). The founder sets `shadow` explicitly.
  - Previously, no row meant `shadow` (TASK-076 decision table).
- Fieldwork screen: preparer and reviewer buttons follow the same roles.
- Copy, following the corpus vocabulary:
  - "Why we need it" (was "Why we ask").
  - "Drafted via Agent, approved by …".
  - "Assess with agent" and "Suggest with agent".
  - "Agent suggests: …" on assessments.
  - "Shadow" and "Live" (was "Trial" and "On").
  - "Agent capabilities" (was "Assistants").
  - "Sign off as preparer" and "Sign off as reviewer"; status "Prepared".
  - "Unpredictable pick".
- Two stale fieldwork screen tests from TASK-087: the second Start button, and `relates_to_year`.

**Out**
- Larger corpus deltas: L1–L5 sign-offs (P-04); materiality as a decision (A-04); sample approval (A-03); Q-02's promotion criteria (QD-10), `agent_stage_events` and planned audit event names. Each needs its own task.
- Request status words ("Ready for review" on requests): this belongs to the request status v2 work (F-03-T15).

## Plan
Approved by founder (2026-10-19, "proceed with your recommendations"). Paths: `docs/architecture/permission-matrix.yaml`, `backend/src/abacus/modules/agents/stages.py`, `backend/tests/unit/agents/test_agent_stages.py`. Approval file: `work/approvals/TASK-089.yaml`, expires 2026-10-26.

## Definition of done
- [x] Stage, boundary and identity unit tests pass; the affected web screen tests pass.
- [x] `make check-fast` passes.

## Progress log
- 2026-10-19: matrix, stages, Fieldwork gating, copy sweep, tests.

## Gotchas and discoveries
- An agent that was shadowing on a real firm with no stage row stops until a row is set. No real firm has opted in yet (the provider-terms register is empty), so nothing is lost.
