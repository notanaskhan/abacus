---
id: TASK-009
title: Write-once evidence storage, per-tenant keys, deterministic rendering
spec: SPEC-000
acceptance_criteria: [AC-12, AC-13]
risk_zone: red
status: todo
branch:
worktree:
created: 2026-10-06
updated: 2026-10-06
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Evidence items and versions; write-once object storage (Versity locally, S3 in staging) with Object Lock; per-tenant envelope encryption; SHA-256 fingerprints; deterministic spreadsheet rendering, tested against a fixture ledger snapshot (real snapshots arrive in TASK-010, which owns AC-10); insert-only enforcement in the database. Wrap `boto3.client("s3")` in a typed kernel factory so the one reasoned pyright ignore from TASK-004 lives in one place.

## Scope
Defined when the plan is written. Starts after TASK-006.

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md`
- ADRs: ADR-004, ADR-016, ADR-035, ADR-042

## Plan
- [ ] Plan approved by human (required for amber and red)
- Red task: the agent drafts the design here; the founder edits or approves it before any code, then reviews the diff line by line (founder decision 2026-10-06).

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

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
- From TASK-005 review: every table passed to `insert_only()` must also be added to `INSERT_ONLY_TABLES` in `schema_check.py`, or the check won't verify it.
- From TASK-006: also declare the app's insertable columns in `APP_INSERT_COLUMNS` and grant them with `insert_columns()`; without a declared list the column check is skipped for that table.

## Questions for the human
-

## Handoff
- **Current state:** Not started.
- **Exact next step:** Write the plan once TASK-006 is done.
