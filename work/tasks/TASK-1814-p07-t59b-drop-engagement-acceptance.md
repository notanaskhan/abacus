---
id: TASK-1814
title: Drop engagement_acceptance; G1 and G2 read the v2 records only (P-07-T59, part 2)
spec: SPEC-332
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-07
plan_key: P-07-T59
branch: s13r-p07-t59b
created: 2026-10-29
updated: 2026-10-29
---

## Objective
The rest of P-07-T59 (DEC-905, DEC-906): SPEC-025's `engagement_acceptance` and every reader go; G1 is the CLI-07 decision alone and G2 the CLI-08 conclusion alone.

## Plan (red)
- **Seeding:** `abacus_tools/fakes/acceptance.py` `open_engagement(conn, tenant, engagement, …)` writes what an engagement past acceptance holds in v2: a backdated seeded questionnaire template version, a `decided` (or `declined`) acceptance record with its decision, and a positive independence conclusion, in one transaction with triggers off (the suites' `run_untriggered` precedent; nothing the app writes changes). Every test support and suite that inserted a legacy row, and `abacus_tools/stack.py`, calls it.
- **Code:** `acceptance_tables.g1_decision` and `independence_tables.g2_met` lose their legacy fallback (`legacy_concluded` goes); `setup.require_open` reads `g1_decision`; `_blocked` takes the G1 decision; the acceptance file attachment (`POST/GET …/acceptance/file`, `attach_acceptance_file`) goes with the table (the letter's file stays on `engagement_letters`); `EngagementAcceptance`, `latest_acceptance`, `add_acceptance` and the registry rows go.
- **Migration 0321** (on 0320): refuses to upgrade while a non-synthetic firm holds a legacy row (P-38: only synthetic data may be dropped); drops the trigger, its function and the table. Downgrade recreates the table as 0036, 0085 and 0175 left it (empty).
- **Tests:** unit `_blocked` cases take a G1 decision; generated tenant-isolation list regenerates.
- **Rollback:** downgrade 0321 and revert; legacy rows are not restored (none exist on a real firm by the refusal).
- **Security:** G1 and G2 can only be met by rows their guards wrote (decider is a partner-level EP with fresh MFA; conclusion is the EP's); no fallback path remains.

## Progress log
- 2026-10-29: built. `abacus_tools.fakes.acceptance` (`open_engagement`, `open_engagement_at`, `withdraw_conclusion_at`); `open_engagement` on the five suite seeders (security, backfill, agent tests, trust kit, undo) and the four inline ones (retrieval, retrieval workflow, retrieval API, evidence); 21 legacy inserts swapped by script, each keeping its decision, conclusion and decision time. G1, G2, `require_open`, the record's gate rows and `gates._independence` read v2 only; the acceptance file routes, `attach_acceptance_file`, `EngagementAcceptance`, `latest_acceptance` and `insert_acceptance` are gone. Migration 0321 (single head on 0320). Unit `_blocked` and C1 gate tests take CLI-07's decision and CLI-08's conclusion (136 passed).
  Tests changed under the approval:
  | Test | Change | Why |
  |---|---|---|
  | P-07-T41 H1 app-written conclusion | removed | the table it wrote is dropped; H1 now holds by construction |
  | P-07-T41 H1 route gone | counts no legacy rows; asserts the table is gone | same |
  | F-04-T16 business time | through `confirm_independence` (CLI-08) instead of SPEC-025's retired route | the write stamped with business time moved |
  | P-04-T19 attest G2 | withdraws the seeded v2 conclusion instead of nulling the legacy one | G2 reads v2 only |
  | independence gate suite | seeds through `open_engagement` (decision, conclusion) | same |
