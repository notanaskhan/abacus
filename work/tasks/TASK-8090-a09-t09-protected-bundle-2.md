---
id: TASK-8090
title: "A-09-T09: S46 protected bundle #2 (group-audit flags, capability, C16 kinds, baselines)"
spec: SPEC-658
acceptance_criteria: [AC-0]
risk_zone: red
status: in-review
branch: a09-t09-protected-bundle-2
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: A-09-T09
---

## Objective
The group-audit rollout and variant flags, the `group_audit` capability in `/v1/me`, the six C16
kinds and the reserved eval baselines, as one protected bundle.

## Plan (red)
- Registry: `docs/architecture/feature-flags/assurance.yaml` (`ledger.consolidation`,
  `assurance.group_audit`), `agents.yaml` (`prompt.ledger.tb_mapper`,
  `prompt.consolidation.elimination_proposer`); owner notanaskhan; default off; created
  2026-11-15, expire 2027-02-12 (89 days, outside every release window). The plan's 2028 dates
  are the plan calendar; the registry takes real dates.
- Regenerated `backend/src/abacus/kernel/_flags.py` (generator, never by hand).
- `platform/capabilities.py`: `group_audit_on` (entitlement and both flags) and the derived
  capability `group_audit` in `/v1/me/capabilities`; `group_audit` joins `REVIEWED_MODULES`, so a
  non-synthetic firm holds it only once the consolidation golden-review memo is registered.
- Six kinds in `notifications/catalogue.py` with text and NotificationKind codes.
- `evals/baselines.yaml`: rows reserved (inferred; A-09-T41 sets them).
- Rollback: revert the PR and regenerate.

## Built
As planned; `tests/unit/platform/test_a09t09_group_audit_bundle.py` (9 pass): registered and
default off, 89-day expiry outside every window, a window expiry refused, the capability truth
table, the reviewed module, the six kinds.

## Human to-do
- Protected-path approval for `_flags.py`, the registry files and `evals/baselines.yaml`.

## Progress log
- `2026-11-15` — Built (DEC-5069). Lesson: tests in `tests/unit/platform/` shadow the stdlib
  `platform` when the folder runs alone; run them with another file first or in the full suite.
