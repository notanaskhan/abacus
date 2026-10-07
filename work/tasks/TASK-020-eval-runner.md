---
id: TASK-020
title: Evaluation runner, graders and calibration
spec: SPEC-005
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16]
risk_zone: amber
status: todo
branch:
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
Implement SPEC-005: one evaluation runner that runs any agent's suite through the real agent path and the AI gateway in evaluation mode. It then grades the cases (deterministic graders first), measures calibration, and gates the run on thresholds weighted toward the dangerous error, calibration and cost. It stores immutable evaluation runs, and lets the gateway use a cheaper tier or fallback model only after a passing run.

## Scope
All of SPEC-005 (AC-1 to AC-16), once approved.

SPEC-005 approved by the founder on 2026-10-07 (all recommendations, Q1–Q8). Next: the design, for founder review.

Excluded:
- the learning loop (ADR-068);
- production drift monitoring (ADR-082);
- consented and firm-scoped cases;
- human sampling;
- a results page;
- suites for agents that don't exist yet.

Real-model runs need a provider (TASK-014): until then the machinery is proven with `FakeModel`.

## Context to load
- Spec: `docs/specs/SPEC-005-evaluation-runner.md`
- ADRs: ADR-076, ADR-081, ADR-082, ADR-070, ADR-055, ADR-047, ADR-068, ADR-072, ADR-073, ADR-083, ADR-085, ADR-019
- Code:
  - `evals/` (`conftest.py`, `screening/test_screening_evals.py`), the `evals` target in the `Makefile`
  - `backend/src/abacus/ai_gateway/` (`call`, `FakeModel`, prompts registry, usage records, admission)
  - `backend/src/abacus/modules/agents/spec.py` and `specs/evidence.screener.yaml` (`evaluation_suite`, `cheaper_tiers`, `confidence_routing`)
  - `backend/src/abacus/modules/agents/citations.py` (citation verifier)
  - `backend/src/abacus_tools/synthetic/` (SPEC-001 generator, flaws)
  - `.github/workflows/ci.yml` (stages)
- Reference: `docs/product/failure-taxonomy.md`; `docs/architecture/reference/` (backend module, unit of work)

## Plan
- [ ] Plan approved by human

### Design (for founder review)
Not started: waits for SPEC-005 approval.

### Steps
1. Design and interface contract, after the spec is approved.
2. Implementation.
3. Independent tests (ADR-078), reviews, `make check`, PR.

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
- `2026-10-07` — Created with SPEC-005 (draft) for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
-

## Questions for the human
- SPEC-005 open questions Q1–Q8.
- Glossary entries "evaluation run", "grader", "calibration" and "dangerous error" (protected).

## Handoff
- **Current state:** SPEC-005 drafted (branch `spec-005-evals`); waiting for founder approval.
- **Exact next step:** once SPEC-005 is approved, write the design in *Plan* and stop for approval.
