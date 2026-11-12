---
id: TASK-7405
title: "T-05-T22: Partner TIN sealing and TRI: partners.tin_sealed and tin_last4 through P-12, tin.reveal with not_offshore and mfa_recent, TRI tags, the data_subjects resolver, retention record types tax_workbook and preparer_memo with legal-hold coverage"
spec: SPEC-651
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: s38-t05-t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: T-05-T22
---

## Objective
A partner's TIN is sealed and revealed only by an onshore person with recent MFA (never in an
audit row); the entity return's data subjects resolve to the partnership; its workbook and memo are
retention record types kept under legal holds.

## Plan (red)
- Migration `0831_tax_partner_tins` (on 0830; M3): `partners.tin_sealed bytea`, `tin_last4`,
  `tin_kind` (all three or none), column-granted; `partner_tin_reveals` (insert-only by trigger, a
  person's row bound to the session GUCs, reason codes as P-07's).
- `tax/partner_tins.py` (red, named in protected-paths): `seal_partner_tin` (after
  `tax_ownership.edit`; envelope bound to the partner, AAD `partner_tin:<id>`; audit
  `partner.updated` with `tin=1`), `reveal_partner_tin` (`tin.reveal`: `mfa_recent`,
  `not_offshore`, a reason; one reveal row and `partner_tin.revealed` naming the reason; the
  DEC-232 hourly cap), `masked`.
- `tax/entity_tri.py` (red): `TRI_RECORDS` (the stored TRI values), `entity_return_subjects` (the
  partnership for the return's year; unknown fails closed), `retain_until`, `on_hold`,
  `releasable` (no policy, no floor, a hold or an unknown return keep the record).
- Cross-module: `engagements.api.work_item_tri_subject`, `evidence.api.engagement_on_hold`,
  `evidence.retention.RECORD_TYPES` += `tax_workbook`, `preparer_memo`, `organisations.api`
  exports `normalise_tin`, `RevealReason`, `TinKind`.
- Tests: `tests/integration/agent_tests/test_t05t22_partner_tins.py`,
  `tests/integration/test_s38_migrations.py` (0831).
- Rollback: downgrade drops the reveals table and the TIN columns.

## Partial
- No route yet: the partner rail (TXP) and its reveal control arrive with the T-05 screens; the
  workbook stub's `…/partners` route stays 501 until the T-05 services.
- The retention years are content (P-14's policy import); until they are loaded a workbook or memo
  version is never releasable.
- Audit catalogue entries for `partner.updated` and `partner_tin.revealed` at the end pass.

## Progress log
- `2026-11-12` — Built (S38). Lint and types clean; tests run at the end pass.
