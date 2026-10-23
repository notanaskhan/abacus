---
id: TASK-972
title: Q-01 close-out docs and skills - infra README final, environments, infra-terraform skill, observability note, platform-ops frozen, capacity ledger (Q-01-T57)
spec: SPEC-050
acceptance_criteria: [AC-6, AC-21]
risk_zone: green
status: in-review
epic: Q-01
plan_key: Q-01-T57
branch: s5-ops-closeout
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"TASK-014 is done with every DoD box checked, and a session adds an egress host by following the skill without apply rights" (Q-01-T57; Q-01 F10).

## Plan
- `infra/README.md` final:
  - a section 0 with the layout and the rules for sessions (plan only, never apply, nothing identifying committed, the egress-host register rule);
  - the portal edge section (TASK-971).
- `docs/ops/environments.md` (new). It covers:
  - local, test, evaluation, previews, staging, production and sandbox: what each holds, its model route, identity, email and who changes it;
  - the rules (ADR-087; never point a local build at a hosted database);
  - the hosts;
  - the staging mail sink, which the platform-ops contract section 3.8 points to.
- `.claude/skills/infra-terraform/SKILL.md` (new): what a session may run, and the recipes for adding an egress host (with the sub-processor register row), a bucket or a service.
- `.claude/skills/observability/SKILL.md`: a platform-side note.
- `docs/contracts/platform-ops.md` frozen at v1, and the register row in `docs/contracts/README.md`. The live parts are pinned by `backend/tests/contracts/platform_ops/test_platform_ops_frozen.py`, because the contract has no OpenAPI models for the snapshot tool.
- `docs/product/capacity-ledger.md` (new), with Q-01's rows by state from the task files.
- TASK-014: close it if its AC-21 evidence exists.

## What changed
- As planned, except TASK-014. **TASK-014 is not done, and the row's acceptance is not met on that half.**
  - There is no AC-21 evidence: no staging environment exists. The landing zone is in progress and nothing is applied.
  - Marking it done would be false. TASK-014's progress log and hand-off now say this and list what has landed.
  - AC-21 can only be recorded after a real `deploy-staging.yml` run with Stories 1 to 6 passing on staging.
- The skill's egress-host recipe was dry-run in this session:
  - an unregistered host written into a `domains = [...]` list made `python -m abacus_tools.codegen.sub_processors --check` fail, naming the host and the file;
  - with the file removed, the check passed again.
  - The passing half (a row added) is covered by `tests/unit/quality/test_sub_processors.py` (TASK-916).
  - No apply rights or credentials were used.
- The capacity ledger records rows delivered, not hours: the task files carry no effort data.

## Not done (needs the builder)
- TASK-014 `done`. It needs the landing zone finished, then Q-01-T07, T14, T15, T17, T18 and T20 applied and run on staging, then the AC-21 smoke recorded.

## Progress log
- 2026-10-23: `validate_docs` passes, and so does the new contract test (5). The egress-host dry run passes as described above.
