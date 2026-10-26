---
id: TASK-1325
title: Independence live, CLI-08 (P-07-T41)
spec: SPEC-332
acceptance_criteria: [AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-27, AC-28]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T41
branch: s10b-independence-intake
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Margaret Okonkwo concludes only after all five confirm, NAS is evaluated and conflicts are
cleared, and G2 then reports met." Turn the CLI-08 independence stubs (501) live.

## Plan
- **Migration 0175 `independence_v2`** (down 0172): `independence_confirmations` + `statements`,
  sealed `interests_note` and `decline_note`, `reminder_count`, `last_reminded_at` (grants);
  insert-only `independence_conclusions` (human CHECK, guard: the acting person, a partner-level
  EP; one successor each, one first per engagement), `nas_evaluations` + `nas_evaluation_events`,
  `independence_breaches` + `independence_breach_events` (each kind once); person columns bound to
  `app.actor_id` (0165's `acting_person_is`); `abacus_human_only_actions()` = 0168's 40 +
  `independence.concluded`, `nas.evaluated` (42). Reversible.
- **Registry and protected files**: `engagements/registry.py` (tables, insert-only, columns),
  `human-only-actions.yaml` + generated `_human_only_actions.py`, banned pattern INDEP-001,
  `error-codes.yaml` (`--write`), generated tenant-isolation tests.
- **Service** `engagements/independence.py` (+ `independence_tables.py`): summary, rotation, NAS,
  confirm, decline, NAS evaluation, breaches, conclusion; organisations
  `standing_conflict_results` (via `organisations.api`); G2 provider and SPEC-025's open gate read
  the conclusion row (else the legacy conclusion) and open breaches; reminders count.
- **Contract**: routes from 501 to live; `MemberConfirmationOut.annual_confirmed` (additive, read
  from G-01); `make generate`; contract doc; the stub contract test moves the routes to LIVE.
- **Tests**: P-07-T43's suite (TASK-1323) with its markers removed.
- **Rollback**: revert the commits and downgrade 0175 (restores 0168's register).

## Coordination
G-01-T13's annual confirmation (identity) is reused through `has_current_annual_confirmation`, not
duplicated. The human-only register is redefined from main's 40-entry list (0168).

## Progress log
- 2026-10-26: planned and built (DEC-428). Deviations: the annual confirmation is read into the
  summary but does not join the cleared predicate (DEC-428 gives the reason); `not_self` is not
  reachable through the routes; rotation's threshold is the platform default 7; the EP's decline
  notification waits on P-07-T47's kind. The legacy G2 rule keeps its pure form in `_blocked`
  (g2 None reads SPEC-025's row) so its unit tests stand; `test_gates.py` patches the two new
  reads. The T43 suite's markers were removed; one other edit to it: its breach-log delete probe
  had a `# noqa: S608` that SUPPRESS-001 refuses, rewritten as two literal statements (same
  assertions).
- 2026-10-26: targeted pass green (see the wave report); gates green.
