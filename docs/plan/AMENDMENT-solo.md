# Solo edition amendment

**Dated 2026-10-20.**

The plan and the prompt books are now for one builder (Ayush) driving Claude Code sequentially: setup, phases PH0 to PH7, sprints S0 to S74, epics, tasks. This amendment overrides every statement to the contrary in `docs/plan/`.

## What this amendment overrides

1. **Roles.** There are no founder roles, lanes, owners, leads or "other founder". Read any such reference as "the builder".
2. **Approvals.** No plan approvals, approval files (`work/approvals/`), `approved_by`, plan approvers, or "stop and wait". Amber and red zones mean: write the plan into the task file first, then build.
3. **Tests.** The ADR-078 split (tests written by another person) is void. Write the acceptance tests first, from the spec, then implement until they pass. Never edit a test to make it pass.
4. **Governance.** CODEOWNERS, rulesets, branch protection, the two-founder hook, protected-path approvals, permission deny lists, number-block reservations, merge windows, the release train and hold-for-batch labels are void. The repo stays public; never commit a secret or real client data.
5. **Worktrees.** Worktree isolation is void. Work on a short branch `TASK-<nnn>-<slug>`.
6. **Review.** Optional self-review with the reviewer subagents (architecture, security, test, AI, contract, design fidelity). It blocks nothing.
7. **Decisions.** Decide in the session, using the plan's proposed option as the default. Record it in `docs/product/decision-log.md` or an ADR, and carry on. There are no Decision Day or contract-sync meetings.
8. **Numbers.** TASK, SPEC and ADR numbers are the next free number on `main`.
9. **Merging.** `make check` green, then merge to `main`. Deploy staging once at sprint close.
10. **Missing dependencies.** Name the task to run first, or build the minimal contract stub (library L02) and carry on.

## What is unchanged

Every ID (phase, sprint, epic, task, screen, DEC, P, ADR, SPEC, journey, milestone), date, path, make target and acceptance string. All product and engineering correctness rules: `tenant_session()`, `authorise()` and `visible()`, audit events, unit of work, immutable evidence, single Alembic head, `make generate`, Brightwater Hale fixtures with the demo clock, tokens and kits only, copy verbatim from the handoff, agents propose and a named human decides in the product, `ai_gateway`, code computes and the model judges, eval suites, synthetic data until the real-data gate (M7).

## Precedence

This file and chapter 08 (`08-collaboration.md`, solo edition) win over any other chapter on process. Chapter 01 still wins on dates and scope.
