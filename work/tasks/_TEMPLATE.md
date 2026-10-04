<!-- Location in repo: work/tasks/_TEMPLATE.md -->
<!-- Copy to work/tasks/TASK-XXX-short-name.md. One task = one session where possible. -->

---
id: TASK-XXX
title: <What this task delivers>
spec: SPEC-XXX
acceptance_criteria: [AC-1, AC-2]
risk_zone: green         # green | amber | red
status: todo             # todo | planning | awaiting-plan-approval | in-progress | blocked | in-review | done
branch: <branch name>
worktree: <path, if parallel>
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
<One sentence.>

## Scope
**In**
- 

**Out**
- 

## Context to load
- Spec: `docs/specs/SPEC-XXX-….md` (sections: …)
- ADRs: 
- Code: 
- Reference pattern to copy: 

## Plan
- [ ] Plan approved by human (required for amber and red)

Steps:
1. [ ] 
2. [ ] 
3. [ ] 

Files to create or change:
- 

Tests to write (mapped to ACs):
- AC-1 → 
- AC-2 → 

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

Commands:
```
<typecheck command>
<lint command>
<test command>
<arch-rules command>
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| | | | |

## Progress log
Append-only. Newest at the bottom.

- `YYYY-MM-DD HH:MM` — <what was done; gate results>

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | yes / no |

## Gotchas and discoveries
- 

## Questions for the human
- [ ] 

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:**
- **Exact next step:**
- **Uncommitted or partial work:**
- **Known failing checks:**
- **Open issues:**
