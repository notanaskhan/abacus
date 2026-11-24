---
id: TASK-8924
title: "C-02-T40: POR-16 write-grant consent v2 (portal)"
spec: SPEC-700
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s53-c02t40
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: C-02-T40
---

## Objective
Row acceptance: "Tess Moreno grants and revokes the write scope with fresh MFA and sees 'Posted 6 journal entries · batch 2026-08-A' in the details drawer." QBO consent sheet with will/won't rows, 'post entries you approve' only when the firm holds W1 for a non-attest client, read-only copy for attest clients, Export instead beside Connect (DF-19), details drawer with write rows, revoke.

## Done
- catalogue: detail_copy.write_consent (consent v2) on the QBO row, writes [ledger_post_journal_entries]; import validation
- card write scope (offered / granted / read_only, can_change) behind the catalogue consent and the firm holding W1; latest_grant helper
- details drawer writes (posted batches, closing date) from the registered posting log
- POR-16: Allow posting… (consent sheet v2, toggle-gated, mfa_required step-up), Turn off posting… confirm, granted tag/caption/disconnect copy, Changes in your books
- fixtures: W1 option on connectionsHandlers (stateful grant/revoke), QUICKBOOKS_WRITE_CONSENT, write log from scenario.cls11-console.json
- tests: unit test_c02t40_write_scope (5), catalogue content test updated for the declared write; vitest POR16.w1 (6) + a-g unchanged (16)

## Progress log
- `2026-11-23` — Built the posting scope end to end; human remainder: counsel review of the v2 words (C-02-T11).
