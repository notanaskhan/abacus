---
id: TASK-9034
title: "T-06-T54: Agent wiring for the entity-depth modes (partly)"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-t06-t54-agents-off
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: T-06-T54
---

## Objective
Agent wiring: asset_evidence, sourcing_position, provision_explainer, time_study_allocation behind their flows; agents-off paths render 'Prepared without agents' and make zero gateway calls.

## Done
- With consent missing for Ashford the Explain flow still creates the issue and records zero gateway calls (held by T-06-T56's test)
- TXP-13 b2 says Prepared without agents when no run starts
- REST: register the four mode prompts and mode_activity branches (red, carried)

## Progress log
- `2026-11-27` — 2026-11-27: partly, per DEC-6039. The agents-off path and its note are built. The model paths are held because the prompts are not registered and the workflow branches are missing. Carried as T-06-T54 rest.
