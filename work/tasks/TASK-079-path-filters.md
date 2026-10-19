---
id: TASK-079
title: CI path filters — backend suites report success on frontend- or docs-only changes, plus a frontend job (epic F-01-T07)
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: red
status: in-review
branch: task-079-path-filters
worktree:
created: 2026-10-19
updated: 2026-10-19
---

## Objective
A frontend- or docs-only change gets its stage 2 results without running backend shards, a backend change still runs everything, and agent-path changes still run stage 3 (epic F-01-T07).

## Scope
**In**
- `abacus_tools/ci/paths.py` (new): classifies a diff into `backend`, `frontend`, `agents`; the single source for every filter in `ci.yml`. Standard library only. Unknown base or a git failure runs everything.
- `ci.yml`: a `changes` job feeds every stage 2 job; each job always runs and reports success, skipping its suite when its paths didn't change, so check names stay stable. New `stage 2 frontend tests` job (Vitest). Stage 3 uses `agents` instead of its own grep.
- `Makefile`: `ci-frontend` (Vitest) split out of `ci-contracts`; `check` runs both.

**Out**
- Playwright fixture smoke and axe slot (wait on F-05 fixture mode).
- Re-recording `durations.json` (follow-up).

## Plan
Approved by founder (2026-10-19, auto mode): paths `.github/workflows/ci.yml`, `Makefile`, `backend/pyproject.toml` (S603 exemption for the git diff, as `secrets_scan` has); approval file `work/approvals/TASK-079.yaml`, expires 2026-10-26.

Docs-only means `docs/adr/**.md`, `docs/specs/**.md`, `work/tasks/**.md` and READMEs; not `docs/product/` (a unit test reads the failure taxonomy) and not YAML under `docs/` (it feeds the code generators). Stage 1's `validate_docs` still checks ADRs, specs and tasks.

Tests: `backend/tests/unit/tools/test_paths.py` (written in this session; the founder waived ADR-078's separate test author on 2026-10-19).

## Definition of done
- [x] `test_paths.py` passes (23 tests); the classifier runs under the runner's plain `python3`.
- [x] `make check-fast` passes.
- [ ] CI on the PR: `changes` reports `backend=true` and the suites run.
- [ ] A docs-only push to `main` skips the backend suites and stays green on them.

## Progress log
- 2026-10-19: classifier, tests, workflow and Makefile changed.

## Gotchas and discoveries
- The contracts job is renamed `stage 2 schema and api-client` (Vitest moved to `stage 2 frontend tests`). No ruleset requires either name today.

## Questions for the human
- None.

## Handoff
Waiting on CI, then merge to `main` and delete `work/approvals/TASK-079.yaml`.
