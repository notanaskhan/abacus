---
id: TASK-7603
title: "W-02-T03 protected bundle: matrix rows, two flags, drill and run-artifact stubs"
plan_key: W-02-T03
spec: SPEC-653
acceptance_criteria: [AC-V4, AC-L5, AC-R3]
risk_zone: red
status: in-review
branch: w02-t03-protected
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The protected bundle W-02's stubs need: the session and run-artifact matrix rows, the
`workbench.enabled` and `workbench.plans` flags, and 501 stubs for the drill, the run-artifact
preview and the download in `agents`.

## Plan
- `permission-matrix/workbench.yaml`: DEC-87's list conditions and the owner-only manage rule
  documented on the existing `session.*` cells (the service applies them; no cell change).
- `permission-matrix/agents.yaml`: `run_artifact.download` (the `run_content.read` principals,
  independence and `not_offshore` required, agent and system denied).
- `feature-flags/workbench.yaml` (new): both flags, default false, owner notanaskhan, created
  2026-11-12, expires 2027-05-07 under DEC-137 (as the P-02 flags).
- `agents/run_artifacts_contract.py` (new): `GET /v1/run-artifacts/{id}/preview`
  (`run_content.read`), `GET …/download` (`run_artifact.download`), `POST
  /v1/workbench/sessions/{id}/drill` (`session.manage`); flag 404, then 501. Registered in
  `agents/api.py` `ROUTERS`.
- Regenerated `_matrix.py`, `actions.gen.ts`, `_flags.py`, the generated security tests.
- Test `backend/tests/unit/workbench/test_w02t03_protected_bundle.py`.
- Rollback: revert; both flags are off and nothing calls the stubs.

## Deviations (DEC-4603)
- Download takes a new `run_artifact.download`, not evidence's `export.create`: that action is
  the binder export (engagement partner and manager only, engagement-scoped), so a staff owner of
  a session could not download their own run's workbook.
- Preview takes `run_content.read`, not `agent_run.read`: the sheet is content, and
  `agent_run.read` without `run_content.read` is the trace's metadata (DEC-87).
- Flags expire 2027-05-07 (the repository calendar, DEC-137), not the epic's 2028-07-31.
- "I-AGENT-NEVER rows regenerated": the generated security tests regenerate from the matrix.

## Progress log
- `2026-11-12` — Bundle built (DEC-4603). Tests run at the S40 end pass.
