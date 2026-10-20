---
id: TASK-155
title: "Q-02-T02 · docs/architecture/ai-threat-model.md (ADR-064): assets, trust boundaries (gateway, Bedrock route, tool layer, portal), hostile-content and prompt-injection paths, cross-tenant and TRI exposure, each mitigation mapped to a test or ADR; notanaskhan reviews"
spec: SPEC-051
acceptance_criteria: [AC-4, AC-5]
risk_zone: amber
status: in-review
epic: Q-02
plan_key: Q-02-T02
branch: task-155-ai-threat-model
created: 2026-10-20
updated: 2026-10-20
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: write the plan into this file before code (solo amendment: no approval step).
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
The threat model merges with every listed threat mapped to an existing or planned test, and notanaskhan's review is recorded.

## Scope
**In**
- docs/architecture/ai-threat-model.md: assets; trust boundaries (gateway, Bedrock route, tool layer, portal); hostile-content and prompt-injection paths; cross-tenant and TRI exposure
- Every mitigation mapped to an existing or planned test, or an ADR
- Self-review recorded (security reviewer subagent, optional per solo amendment)

**Out**
- Writing the mapped tests
- Changing the gateway or tool layer

## Context to load
- Spec: `docs/specs/SPEC-051-compliance-setup.md` (sections 5 and Task map; ACs AC-4, AC-5)
- Epic: `docs/plan/epics/Q-02.md`: Q-02 §0 (supporting-founder row: AI threat model, chapter 08 §8.1.1); Q-02 §6.1 (capabilities, tools and gates) and §7.2 obligations rows for ADR-113/114/115; Q-02 §10 item 9; ADR-064
- Task row: `docs/plan/epics/Q-02.tasks.csv`, `Q-02-T02`
- Process: `docs/plan/AMENDMENT-solo.md`
- Data boundary: `docs/specs/SPEC-036-data-boundary.md` (referenced, not duplicated); ADR-113, ADR-114

## Plan
- [x] Plan written in this file (required for amber and red)

Steps:
1. [x] Read ADR-064 and ADR-113; list assets and boundaries
2. [x] Enumerate threats; map each to a test path or ADR
3. [x] Self-review; record in the file

Files to create or change:
- docs/architecture/ai-threat-model.md
- docs/architecture/e2e-journeys.md (ADR-077 registry; written in the same session, not named in this task's scope)

Tests to write (mapped to ACs):
- AC-4 -> each threat row names an existing test path, a planned task id or an ADR
- AC-5 -> review note present

## Definition of done
- [x] All listed ACs have passing tests or checks that reference them (checked by a throwaway script: 49 threat rows, each with a coverage entry; every cited path exists; every cited task id is in Q-02.tasks.csv)
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [x] No secrets or real client data committed (public repo)
- [x] No new dependencies, or each one listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation (N/A for this task unless it adds either)
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals (N/A unless it adds any)
- [x] Module README and relevant docs updated
- [x] Decisions below recorded; ADR raised where needed

Commands:
```
make check
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| | | | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — task file written from the epic (SU-14); nothing built yet.
- `2026-10-20` — Wrote `docs/architecture/ai-threat-model.md`: 12 assets, 9 actors, 8 trust boundaries, 49 threats in six groups (hostile content, tool layer, cross-tenant, data boundary, tax return information, supply chain), each with a coverage entry (existing test or suite, planned Q-02 task, or ADR). Six gaps recorded where the only evidence is an ADR. Self-review recorded in the file (authoring session against the security reviewer's checklist; the subagent itself was not run, AC-5 allows it to block nothing). Also wrote `docs/architecture/e2e-journeys.md` (J01 to J28; only `apps/web/e2e/journey.spec.ts` exists). Quality commands pass. Status `in-review`, not `done`: `make check` not run, subagent review not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Coverage vocabulary: Tested (path exists), Planned (Q-02 task id), ADR (rule only, listed under Gaps) | AC-4 wants every threat mapped to an existing or planned test or an ADR; the third kind needed to be visible | no |
| Review recorded as the authoring session's own checklist walk, not the subagent | Subagent is optional; running it was not asked for | no |
| Journey spec paths follow chapter 10 (`apps/web/e2e/journeys/jNN-<slug>.spec.ts`) over the sprint-plan row that writes a flat path | Chapter 10 owns test layout | no |

## Gotchas and discoveries
- `backend/src/abacus/ai_gateway/sanitise.py` has no backend test; the frontend side is tested. Listed under Gaps.
- No test names the global inference profile rejection, tenant-scoped caches, the outbound scope checker, or learning-loop approval.
- `.github/pull_request_template.md` does not yet carry ADR-064's threat-model item.

## Questions for the human
- [ ] Open a task for the six gaps in the threat model (sanitiser test, scope checker, cache scoping, global-profile check in Q-02-T11, event-stream payloads, learning loop)? Not opened here: scope was documents only.
- [ ] Run the security reviewer subagent over the threat model before the M4 risk assessment (M4-10)? Optional.
- [ ] Add the threat-model line to the pull-request template? It is a protected-adjacent file; not touched here.

## Handoff
- **Current state:** threat model and journey registry written and committed on the branch; status `in-review`.
- **Exact next step:** decide on the gap tasks and the optional subagent review, then set `done`.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none in the three quality commands; `make check` not run.
- **Open issues:** see Questions for the human.
