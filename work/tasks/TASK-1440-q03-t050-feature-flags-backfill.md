---
id: TASK-1440
title: Back-fill TASK-026, the feature-flag registry, from SPEC-011 (Q-03-T050)
spec: SPEC-011
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-6]
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T050
branch: s11-trust-tests
test_author: ayushkbhatia
test_session: 2026-10-27, branch s11-trust-tests (S11 lane 7; a clean session following .claude/skills/ac-test-author/SKILL.md, from the spec, contracts and ADRs only)
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"The suite proves a flag cannot enable a module that the firm's entitlements refuse."

## Plan
- **File:** `backend/tests/integration/backfill/test_q03t050_feature_flags.py`: the registry
  files, the validator SPEC-011 §8 names, `kernel.flags.flag`, the operator's `set_flag`, and
  `GET /v1/engagement-types` over HTTP. Entitlements seeded as the superuser (operator only).
- No production change. Rollback: delete the file.

## Results (25 tests, all pass)
- AC-6: every entry has owner, description, a 90-day lifetime or a named DEC override up to 180
  days (DEC-137), a valid default; the validator refuses 91 days, 181 with override, a bare
  override, no owner, blank description, a bad default, `ff.attest`, `attest.*`, `insights.*`, a
  variant without its default; it accepts 90 and a named 180.
- DEC-55/ADR-148: every name is `area.feature`, none `ff.*`, none in the entitlement modules (read
  from the database CHECK).
- AC-4: `expired` reports the flag and owner the day after; none is expired today.
- AC-1, AC-2, AC-3: default when unset, true when set, per firm; read after the set; an unreachable
  database reads the default and logs `flag.read_failed` without the DSN; the set is audited as
  `operator:<name>` with both values, stored with name and reason; unknown flags and values refused.
- Q-03-T050: with every boolean flag on, `check_entitlement` refuses every module and SOC 1/2 stay
  `needs_entitlement`; with the `attest` row they are available; the catalogue's rollout flag off
  answers 404 even for an entitled firm.

## Spec drift followed
- DEC-137 (override up to 180 days); DEC-55/ADR-148 (modules are entitlements).

## Not covered
- AC-5 (FLAG-001 lint) is the banned-patterns rule's own test; AC-7/AC-8 (prompt variants) need a
  registered alternate prompt.

## Progress log
- 2026-10-27: suite written; targeted pass: 25 passed.
