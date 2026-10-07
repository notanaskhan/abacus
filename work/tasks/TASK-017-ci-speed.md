---
id: TASK-017
title: Faster CI (parallel stage 2)
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: amber
status: in-progress
branch: task-017-ci-speed
worktree:
created: 2026-10-07
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
Cut CI stage 2 from about 28 minutes in one job (stage 1 repeated, unit 5 min, integration 21 min) by running `make check` as parallel jobs, without dropping any check or test.

## Scope
`.github/workflows/ci.yml`, `Makefile`, and a new `abacus_tools.ci.shard` with its timings file. No new dependencies; `make check` stays the one-machine equivalent.

## Context to load
- ADR-083 (CI stages), ADR-079 (coverage floor), ADR-010 (Makefile is the command surface)

## Plan
- [x] Plan approved by human (founder, 2026-10-07: "make the ci quicker in the best ways possible")
- Approved by founder: paths `.github/workflows/ci.yml`, `Makefile` (local approval file `work/approvals/TASK-017.yaml`).

1. `abacus_tools.ci.shard`: split test files into N shards, greedy longest-first on recorded seconds per file (`backend/tests/durations.json`). Every file goes to exactly one shard; a new file is weighted as the median.
2. Make targets `ci-unit`, `ci-integration` (`SHARD`/`SHARDS`; each shard writes `.coverage.<suite>-<n>`), `ci-coverage` (combine, then the 95% floor), and `ci-contracts` (schema check, api-client drift, vitest). `make check` reuses them.
3. CI: stage 2 runs 2 unit shards, 5 integration shards, contracts, and a coverage job that combines the shards' data. The aggregate job keeps the name `stages 1 and 2 (make check)` and passes only if every job passed. Stage 1 is no longer repeated inside stage 2.

Not done, on purpose: pytest-xdist (a new dependency, and the integration fixtures share containers), and test selection by changed files (red-zone changes break other modules).

## Definition of done
- [ ] Shard tool tested (every file exactly once, balanced, deterministic)
- [ ] CI green on the PR, with stage 2 wall-clock time recorded
- [ ] Coverage floor still enforced on the combined data

## Progress log
- `2026-10-07` — Implemented the shard tool and tests, the Make targets and the parallel stage 2 (PR #23, merged without waiting for CI).
- `2026-10-07` — PR #23 broke main: a `# noqa: S314` in `shard.py` (SUPPRESS-001). Fixed by reading the plain-text `pytest --durations=0` report instead of JUnit XML. Timings recorded.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Shards by recorded per-file time, not a plugin | No new dependency; deterministic; new files still run | No |

## Gotchas and discoveries
- `.coverage.<suite>-<n>` files aren't git-ignored (`.gitignore` is protected); they only appear when the `ci-*` targets run locally.

## Questions for the human
-

## Handoff
- **Current state:** merged without waiting for CI (founder). Timings recorded in `backend/tests/durations.json` (a full local run; unit shards about 38 s each, integration about 120 s each, locally).
- **Next:** note stage 2's wall-clock time from the first PR run. Then delete `work/approvals/TASK-017.yaml`.
