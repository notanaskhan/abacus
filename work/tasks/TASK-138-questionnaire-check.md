---
id: TASK-138
title: "F-09-T12 · The builder's own check of the security questionnaire answers against commercial terms, the LOI template and every external claim"
spec: SPEC-049
acceptance_criteria: [AC-13]
risk_zone: red
status: todo
epic: F-09
plan_key: F-09-T12
branch: task-138-questionnaire-check
created: 2026-10-20
updated: 2026-10-20
---

> **Rules for the agent working this task**
> - Solo edition: one builder, no approvals, no reviewers to wait for (`docs/plan/AMENDMENT-solo.md`).
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: write the plan below into this file first, then build.
> - If scope must change, add it to *Questions for the human* and carry on with the plan's proposed option.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
No answer promises a control, region or certification that the plan of record does not hold on that date.

## Scope
**In**
- Read each questionnaire answer filed in F-09-T11 and each external claim in the LOI template and commercial terms
- Check every claim against the plan of record on that date: accepted ADRs, the register and DEC records
- Correct or remove any claim that is ahead of the plan; record the check with its date

**Out**
- Filing the questionnaires or the SES and Bedrock requests (F-09-T11, done by hand from SU-26)
- Any claim about a certification not held (no SOC 2 report exists yet)

## Context to load
- Spec: `docs/specs/SPEC-049-vendor-legal-assurance-programme.md` (sections: 5 AC-13; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/F-09.md` §0 (lines 11-29), §3 (127-244), §9 (401-674), §10 (675-696), §11 (697-723); read in full: §3.2 B2 (questionnaires); §9 row F-09-T12 (rewritten here as the builder's own check); §11 R-3
- Row: `docs/plan/epics/F-09.tasks.csv`, plan key F-09-T12
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- Rewritten row: the plan's independent check by the other founder becomes the builder's own check (solo amendment)

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is red)

Steps:
1. [ ] List every claim that leaves the company: region, controls, certifications, data handling
2. [ ] For each, find the accepted ADR or register entry that holds it on the date of the answer
3. [ ] Fix or remove any claim with no source; re-check the LOI wording for INV-1, ADR-111 and DEC-65 promises
4. [ ] Record the check date and result (status only) in the tracker or decision log

Files to create or change:
- docs/ops/vendors/README.md (status line)
- docs/product/decision-log.md (check record)

Tests to write (mapped to ACs):
- AC-13 → review: every questionnaire answer and external claim traced to an accepted ADR or register entry, or removed

## Definition of done
- [ ] Every listed AC is met and has evidence (tracker row, vault record or decision-log entry), referenced by its AC id
- [ ] `cd backend && uv run python -m abacus_tools.quality.validate_docs` passes
- [ ] No price, contract text, partner firm name, counsel advice or secret is in git (the repo is public until F-01-T01)
- [ ] No code changed; no new dependencies
- [ ] Decisions below recorded in `docs/product/decision-log.md` where they bind later work

Commands:
```
cd backend && uv run python -m abacus_tools.quality.validate_docs
```

## New dependencies
| Package | Version | Why | Decision |
|---|---|---|---|
| none | | | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — Task file written at kickoff (SU-14). No work started.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | yes / no |

## Gotchas and discoveries
- Depends on F-09-T11.
- The check is the builder's own; do it after a pause from writing the answers, claim by claim, not as a skim.

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Collect the questionnaire answers from F-09-T11 and list every outward claim.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
