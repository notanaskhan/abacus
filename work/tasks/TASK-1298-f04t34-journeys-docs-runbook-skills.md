---
id: TASK-1298
title: e2e-journeys.md (ADR-077), the demo-tenant runbook, and the fixture-scenario and journey-step skills
spec: none (F-04 §2 docs row; ADR-077)
acceptance_criteria: [F-04-T34]
risk_zone: red
status: in-review
epic: F-04
plan_key: F-04-T34
branch: s9c-viewer-tests-docs
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Doc, runbook and skills are merged" (F-04-T34). `docs/architecture/e2e-journeys.md` and the
`fixture-scenario` and `journey-e2e` skills existed; the demo-tenant runbook and the
`journey-step` skill did not. Bring the registry up to what is built and put the S9 deploy steps
where an operator will find them.

## Plan
- `docs/architecture/e2e-journeys.md`: status as of Oct 26 (J01, J02, J04, J12 have specs on the
  harness), the as-built `JNN-<slug>.spec.ts` naming, the four harness projects and their make
  targets, pointers to the three skills and the runbook. Registry rows only change path and status.
- `docs/runbooks/demo-tenant.md` (the plan's path; a procedure, so no `RB-<nn>` and not in
  `validate_docs`' runbook glob): rules, prerequisites, first load (F-04-T24), reset before a
  session, migration up/down/up on a staging copy, after-deploy one-off steps, verify. S9 steps:
  the `run_record_fingerprint_pepper` secret before the image starts (#422), 0172 up/down/up on a
  restored copy (#424), `python -m abacus_tools.trust_layer_backfill <tenant>` (v2) for every
  tenant after the deploy (#419).
- `RB-01`: one paragraph pointing at the runbook's release-specific sections.
- `.claude/skills/journey-step/SKILL.md` (new); `journey-e2e` and `fixture-scenario`: their
  "paths that arrive later" replaced by the paths that now exist.
- `.claude/` is not protected for agents in the solo edition (`docs/architecture/protected-paths.md`:
  the hooks guard only secrets, generated files and migrations on main), so the skills are written
  in place. The plan's "N approves the protected `.claude/` paths" is void under
  `docs/plan/AMENDMENT-solo.md`.
- No code, migrations, flags or generated sources. Rollback: revert the commit.

## Findings
- **ED-088 (open):** the ops-task allowlist (`abacus_tools.release.OPS_COMMANDS`,
  `.github/workflows/ops-task.yml`) has neither the scenario loader nor
  `abacus_tools.trust_layer_backfill`, so the staging demo-tenant load and S9's backfill have no
  sanctioned way to run. Recorded in the runbook §1 and held for the main session (a
  platform-ops contract change, not a docs change).
- F-04-T24 (the first staging load) and Q-01-T55 (the tenant shell) are still `todo`; the runbook is
  the procedure they will follow and has not been rehearsed (`last_rehearsed: never`).

## Progress log
- 2026-10-26: written. Docs-only; `validate_docs` in the gates run.
