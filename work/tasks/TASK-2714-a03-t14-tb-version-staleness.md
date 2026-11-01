---
id: TASK-2714
title: A-03-T14 TB-version staleness (subscriber, follow_tb_version, mapping_set_stale)
spec: SPEC-580  # A-03 F6 US-6.4 and docs/contracts/ledger-mapping.md §7.1
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-03
plan_key: A-03-T14
branch: s22-a03-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "Adopting Granite Peak TB version 2 with one new account leaves version 1 and its
  snapshot untouched, shows one unmapped account, makes the L1 sign-off compute stale and
  notifies Caleb Dunn and Hannah Leclerc once."

## Scope
**In**: `assurance/mapping.py` subscriber (version 1 creates the set on the firm's one published
grouping set; version n follows and announces stale), `ledger.api.follow_tb_version` and
`version_adopter`, outbox `mapping_set.version_followed` (dedupe), C16 `mapping_set_stale`
(`notifications/catalogue.py`; `sign_off_stale` leaves mapping sets to it), activity review,
contract §7.1, unit and integration tests.
**Out**: A-10's override staleness; AUD-31's e′ banner (fixture, A-03-T12).

## Plan (red)
1. Flag `ledger.tb_mapping` gates the subscriber (off: nothing).
2. Version 1: one published grouping set → create on its newest version as the v1 adopter; none or
   several → a person chooses (DEC-1765, the plan left the default open).
3. Version n: one unit of work records `mapping_set.version_followed` and emits its deterministic
   event (a replay's IntegrityError changes nothing); if the content left sign-offs stale, the
   audit and `mapping_set.went_stale` with the signers as recipients.
4. Notifications: one `mapping_set_stale` per signer; `sign_off_stale` returns no recipient for a
   mapping-set sign-off so nobody is told twice.
5. No migration: mapping is computed on read (ADR-341 §5); the confirm CHECK DEC-1864 mentions is
   a C3 sign-off row, already human-bound (`sign_offs` actor CHECK).
6. Rollback: revert; the subscriber returns to announce-only.

## Progress log
- 2026-11-01: built; unit suite (11) run once (red); integration suite in the S22 end pass.
