---
id: TASK-1229
title: Independent AC suites for firm settings and people, clients and walls, the team and EQR, and the P-07 consumer contract (G-01-T11; P-07-T13, P-07-T31, P-07-T32)
spec: SPEC-321
acceptance_criteria: [AC-6, AC-7, AC-8, AC-9]
risk_zone: red
status: done
epic: P-07
plan_key: G-01-T11; P-07-T13; P-07-T31; P-07-T32
branch: s8b-accept-tests
test_author: ayushkbhatia
test_session: 2026-10-25, branch s8b-accept-tests (one clean session per suite, following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-25
updated: 2026-10-25
---

## Objective
- **G-01-T11:** "The suite is committed against the stubs and passes on T04 and T05 with no edits by N."
- **P-07-T13:** "The suite passes on main without edits by the implementing session and fails if a wall, mask or reveal rule is weakened."
- **P-07-T31:** "The suites ... assert the decision and conclusion option sets and the redacted conflict-row shape."
- **P-07-T32:** "The suite is committed before T30 opens for review and passes unchanged."

## Plan (red zone)
- **Files (tests only):** `backend/tests/integration/backfill/test_g01t11_settings_people_independent.py`, `test_p07t13_clients_walls_tin_independent.py`, `test_p07t32_team_eqr_independent.py`; `backend/tests/contracts/acceptance_independence/test_acceptance_independence_consumer.py` (the existing stub file is unchanged).
- **Production:** one guard in `engagements/service.py` `add_to_team` (ED-053). No migration, route, matrix, flag or registry change.
- **Rollback:** revert the commit.

## Results
- **G-01-T11 (22 pass):** AC1.2 to AC1.8 (fresh MFA, `firm_setting.updated` naming the person, 422 `display_name_required`, 409 `stale_version`, `region` 422 `unknown_setting` and no app-role UPDATE, partner and IT read-only, staff 404); AC3.3 and AC3.4 (`seats_full` with used and total, a pending invitation holds a seat, 14 days, single use, expired joins nothing); AC3.5; AC4.1 to AC4.4 and AC4.7 (role change with fresh MFA and audit, `last_admin` and `firm_role_held`, deactivation keeps attribution, agent and system refused); AC5.1 to AC5.3 (8 templates, 16 capability rows plus the locked agent row, no drift against the compiled matrix, I-AGENT-NEVER).
- **P-07-T13 (36 pass):** walls answer 404 exactly as an unknown id with no count (INV-3, AC-6, AC-7), Grace metadata-only, TIN never in payloads, audit, outbox, logs or at-rest columns (AC-9), reveal rules (one value, `no-store`, one `tin.revealed`, every refusal), the SSN and ITIN guard, attribution (INV-5, AC-8), tenant isolation on the new tables.
- **P-07-T31 (15 pass):** decision and conclusion option sets on request and response, C2 status enums, ENG-05 roster, approval footer and EQR picker, the §8 redacted conflict row with no wall or match count.
- **P-07-T32 (17 pass after the fix):** EQR eligibility (cooling-off, independence, unassessed needs the quality owner first, `eqr_on_team`), approver not the EP, team approval with fresh MFA and the changes-since footer, portal visibility, the blocked assignment.

## Escaped defects
- **ED-053 (fixed):** `engagements/service.py` `add_to_team` had no EQR guard, so `POST …/team` naming the engagement's EQR answered 404, not 409 `eqr_on_team` (acceptance-independence.md §6, DEC-327). Fixed with the same `team_standing(...) == "eqr"` check `change_team_role` makes; `test_ac5_2_adding_the_eqr_to_the_team_answers_409_eqr_on_team`.

## Spec gaps (no defect)
- G-01 AC5.1: the grid returns 17 rows; read as 16 capability rows plus AC5.3's locked agent row.
- G-01: the partner and IT people views are the person drawer and role templates; the list stays on `firm.manage_users` (DEC-286). Create routes accept 200 or 201 (the contract fixes neither).
- P-07-T31: `ConflictClearIn` takes `conflict`, not yet a `conflict_assessment` code; contract §4 says P-07-T36 adds it, so exactly that one extra code is allowed. `PriorAcceptanceOut.option` is an open string with no named vocabulary, so it is not asserted.

## Progress log
- 2026-10-25: four suites written from the specs, contracts and decisions only; one defect found and fixed (ED-053). Commands in the TASK-1229 commit message's branch report.
