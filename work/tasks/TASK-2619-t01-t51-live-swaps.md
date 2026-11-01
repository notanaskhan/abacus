---
id: TASK-2619
title: T-01-T51 live swaps and consumer flips (TAX-12, ADM-08, CLI-02 b, ENG-03 e, BND-01, ADM-04 D, POR-02)
spec: SPEC-501
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: T-01
plan_key: T-01-T51
branch: s21-t01-t51
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"Each consumer shows live C19 and bridge data on staging, and the manifest marks no T-01 link as
planned except NOT-02, TAX-13 and KNW-05." (T-01 §5.)

## Scope
**In**:
- **TAX-12** onto the live reads: every name, date, figure and jurisdiction from final approval,
  engine sync, delivery, the envelope and the seat holders (no Feld constant in code; the copy
  became functions); transmission date is today in the firm's zone, jurisdictions from the
  payment instructions; Create issue (TAX-06, planned) drawn only where planned screens are.
  Routed at `/tax-returns/$returnId/delivery` (behind `tax.returns_v1` and `tax.delivery_efile`);
  manifest `fixture`; links TAX-02 → TAX-12 (Open delivery), TAX-09 → TAX-12 (footer), TAX-12 →
  TAX-09 (Sync history, `ov.TAX09`).
- **ADM-08** in the manifest at `/settings/integrations` (`fixture`); ADM-01 and ADM-05 open it
  from the settings nav; ADM-08 → ADM-01, ADM-05, INB-01 (Unmatched senders), TAX-09 (Last sync,
  new `last_sync_return_id`, filled by tax through `integrations.api.register_last_engine_sync`).
- **ADM-04 D**: the blocked-clients count from C19's summary (new `blocked_clients`) and
  "Consent registry ›" opening ADM-05.
- **CLI-02 b**: the §7216 consents row from C19 (household) and the sync chip on tax-return work
  rows (live `engine-sync`, opens TAX-09).
- **ENG-03 e**: the consents card from C19 for the draft's taxpayer (the fixture preview still wins).
- **POR-02**: "Engagement letter and §7216 consents signed" Earlier rows from the completed G3
  letter envelope (`signatures.api.letter_signed_at`), and View on a filed return downloads the
  client copy.
- **BND-01**: the consents tag was already live (binder rows' counts); nothing to change.
**Deviations (DEC-1667)**: ADM-04 D shows a count, not the three names (the summary is counts
only, by design); a client with no consent row is not counted as blocked. TAX-12's KBA line reads
"KBA passed" without "4 of 4" (the envelope carries no question count). The reminder sheet names
the unsigned signers and the template's purpose; its words are the firm's pre-approved template.

## Progress log
- 2026-11-01: built; tests (TAX-12, ADM-04, CLI-02, ENG-03, POR-02, link contract, summary) at the
  batch's end review.
