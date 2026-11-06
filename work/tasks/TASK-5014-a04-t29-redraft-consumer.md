---
id: TASK-5014
title: A-04-T29 remainder - the re-draft after Internal Control, and AUD-08 e's live state
spec: SPEC-000  # row
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: red
status: in-review
epic: A-04
plan_key: A-04-T29
branch: s26r-a04-t29-redraft
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-06
updated: 2026-11-06
---

# TASK-5014 · A-04-T29: the re-draft consumer

TASK-3220 built mode `ic` and left the consumer out.

AC-1: a completed `ic` run with a risk linked to AUD-09 starts one `risk` run, for the person who
started it, under the same authorisation; redelivery starts nothing more.

AC-2: no run starts with `workpapers.drafting` off, with no linked risk, for a mode other than `ic`,
or for a person no longer allowed. A refusal leaves AUD-08's "Draft with agent" as the fallback.

AC-3: AUD-08 shows "Revising after Internal Control…" from the live register while that run runs.

## Plan (red)
- `agents/events.py` `SectionDraftFinished`, emitted when a run completes.
- `assurance/ic_redraft.py`: the consumer and `revising`.
- `RegisterOut.revising`, the generated client, AUD-08's poll.
- Rollback: a no-op with `workpapers.drafting` off; no migration.

## Decisions (DEC-2327)
The plan names `workpaper.version_created` with producer agent. The agent writes suggestions and
never a version (ADR-005; every version is `produced_by_kind` human), so that event can never carry
it. The trigger is the `ic` run's completion. The consumer sits in `assurance`, which knows the
linkage, not `agents` as the plan says: `agents` may not read assurance's tables.

## Known limits
A risk counts as linked when the matrix has a live or suggested `workpaper` link to `AUD-09`; the
risk mode drafts the whole register, so it is one run per Internal Control run, not one per risk.

## Progress log
- 2026-11-06: built on main 49922a2fd.
