---
id: TASK-8905
title: "C-02-T33: Vendor TIN handling"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-c02t33
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-22
updated: 2026-11-22
plan_key: C-02-T33
---

## Objective
Sealed TINs (ADR P-12), last-4 masking in API, DOM and logs, logged reveal through P-03 pii_reveal (tin.reveal, never offshore), TIN Matching results recorded by a person, backup-withholding events (24% only after a CP2100 B-notice plus 30 business days or a missing TIN); no IRS-login automation. Acceptance: no TIN plaintext appears outside the sealed store, every reveal writes a pii_reveals row naming the person, and an offshore user's reveal is refused.

## Done
- closes/vendor_tins.py: _vendor scope (vendor → entity's latest close engagement; walls and unknown 404), get_vendor (rollups + C21 threshold, last four only), record_w9 (normalise, SSN gated by C19 or a synthetic firm, kernel seal bound to vendor_1099_tin:<id>, per-firm fingerprint, optimistic version, 409 tin_conflict), reveal_vendor_tin (evidence.reveal_field with field_ref vendor:<id>:tin → pii_reveals row naming the person, audit, access record; non-MFA refusal → 403 tin_reveal_refused), record_tin_match (manual, evidence on the close engagement, W-9 status moves), record_backup_withholding (state machine, B-notice needs date + evidence, started at 24% only when due: 30 business days after the latest B-notice with no TIN certified since, or no TIN)
- closes/compute/information_returns.py (pure): classify (processor payments excluded, corporation exempt unless attorney, threshold, NEC box 1), w9_status_after_match, backup_state_after
- Contract: PUT /v1/vendors/{id}/w9 (DeliveryW9RecordIn, SecretStr Restricted tin), backup-withholding notice_received_on; GET vendor, reveal, TIN match and backup routes call the service; docs/contracts/closes-delivery.md rows
- Error codes catalogued (backup_withholding_not_due, backup_withholding_state, tin_not_on_file, evidence_required, stale_version); audit target vendor; reviewed fallback labels vendor.updated, tin_match.recorded, backup_withholding.recorded (identifiers only)
- tests/unit/closes/test_c02t33_vendor_tins.py (27 pass)

## Progress log
- `2026-11-22` — Built in the S53 sequential stack (DEC-5907). Remainder for later rows: CLS-13 list, PATCH classification, W-9 requests and batches (C-02-T45/T46); make generate at the end pass (new route).

## Plan (red)
1. Service `closes/vendor_tins.py` + pure compute; routes wired in `delivery_contract.py`; contract doc.
2. Reveal through P-03's `reveal_field` (no second reveal path); seal through `kernel.crypto.seal`.
3. Tests: compute, reveal mapping (offshore → tin_reveal_refused, MFA passes through), W-9 seal never leaks digits into params/audit/response, SSN gate, evidence scope, matching and withholding rules, static no-log.
4. Rollback: routes return to 501; tables (1013) stay.
