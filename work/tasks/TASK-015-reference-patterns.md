---
id: TASK-015
title: Reference implementations and skills
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: green
status: in-review
branch: task-015-reference-docs
worktree:
created: 2026-10-06
updated: 2026-10-07
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Write the nine reference docs in SPEC-000 §22 to `docs/architecture/reference/` from the merged code, and update the matching skills.

## Scope
Write the six missing SPEC-000 §22 reference docs (`backend-module`, `unit-of-work`, `temporal-workflow`, `connector`, `evidence-storage`, `ai-agent`) from the merged code. `tenancy-and-authz`, `frontend-feature` and `observability` already exist. Update the matching skills to point at them (`.claude/skills/**`, protected; approved). Docs only, no code changes.

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md`
- ADRs: ADR-086

## Plan
- [ ] Plan approved by human (required for amber and red)


Steps: to be written when the task starts.

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|

## Progress log
- `2026-10-06` — Created from the SPEC-000 breakdown approved by the founder. Not started.

- `2026-10-07` — Started (green). The founder approved editing `.claude/skills/**`; the approval file was written at the founder's instruction. Three agents are drafting the six docs from main; the implementer reviews them against the code.
- `2026-10-07` — The six docs are written from main by three agents and checked by the implementer: every referenced path exists, and every named function or class exists in the code or is a library call. The skills are updated (backend-module, temporal-workflow, connector, ai-agent) to match what was built. `validate_docs` passes.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
- **Stale module docs** (protected paths; not changed in this task):
  - `modules/evidence/README.md` shows an old `add_version` signature.
  - `modules/agents/README.md` and the `workflows.py` docstring say `screening:<evidence_version_id>`, but the code uses the tenant-qualified ID. The README says a 2-minute `screen` timeout; it is 5 minutes with a heartbeat.
  - The `connector.py` docstring names `tests/connectors/` (it is `tests/unit/connections/conformance.py`).
- **Gaps against the ADRs, recorded in the docs' "Not yet" sections:**
  - ADR-038's reconciliation checks beyond control totals;
  - ADR-040's egress allowlist and the integration test against write requests;
  - ADR-090: no workflow uses `workflow.patched` yet (the current steps are v1);
  - ADR-031 classification covers Pydantic models only, not SQLAlchemy models;
  - ethical walls (ADR-026) are still not modelled.
-

## Questions for the human
-

## Handoff
- **Current state:** PR open from `task-015-reference-docs`; docs and skills only.
- **Exact next step:** Founder review (ADR-086: every merge needs approval for now). Merge (rebase), delete `work/approvals/TASK-015.yaml`, mark done. Optionally fix the stale module READMEs and docstrings listed in Gotchas, which needs approval for those protected paths.
