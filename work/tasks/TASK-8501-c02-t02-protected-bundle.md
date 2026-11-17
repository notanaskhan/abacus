---
id: TASK-8501
title: "C-02-T02: S49 protected bundle: matrix, flags, W1 registry entry, error codes, kinds, protected paths, POST-001/TJE-001/IRIS-001"
spec: SPEC-700
acceptance_criteria: [AC-1, AC-10]
risk_zone: red
status: in-review
branch: c02-t02-protected-bundle
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-02-T02
---

## Objective
Spec section: docs/plan/epics/C-02.md §4.5, §4.6. Protected bundle: per-module matrix sections (adjustments posting, closes delivery/hand-off/information returns, integrations write grants and capability enablement, connections console), six rollout flags, the W1 entry in write-capabilities.yaml with enabled false, error codes, notification kinds, protected paths and static rules POST-001, TJE-001, IRIS-001.

## Plan (red)
1. Matrix: 10 adjustments actions (approve, request/undo/withdraw approval, reject_close, record_external, export, posting_batch.dry_run/post, closing_date_conflict.resolve), integrations write_capability.enable + gl_posting_settings.read/update + engagement_ledger_settings.update, connections ledger_connection.read/export + connection.grant_write/revoke_write, closes 19 package/lock/reopen/hand-off/1099 actions. Agent and system deny on every one. Existing tin.reveal, connection.read_log and close_package.client_decide reused.
2. Fresh-MFA register: 8 actions, new group `posting` (fresh_mfa.GROUPS).
3. Flags: adjustments.posting (new file), closes.gl_console/delivery/tax_handoff/information_returns/vendor_screen; created 2026-11-17, expire 2027-05-16 (DEC-137 override, as closes.engine).
4. Registry: W1 entry decision ADR-344 with operations, attest_clients refused, policy_principal never, preflight, verify_after read_back, reversal new_write, kill switch; schema `WriteCapabilityEntry` validates the whole W1 policy and refuses it on other shapes; compiler dumps exclude_none; `_capabilities.py` regenerated.
5. Error codes: adjustments/posting_errors.py, integrations/write_errors.py, closes/delivery_errors.py (17 codes), imported from each api.py; catalogue regenerated.
6. Notification kinds: entry_approval_requested, posting_failed, posting_batch_posted, package_client_approved, tax_handoff_received, tax_handoff_superseded, vendor_form_uploaded (C16 codes are letters only) with templates.
7. banned_patterns: POST-001, TJE-001, IRIS-001; protected-paths.md names the three red files.
8. Tests: tests/unit/adjustments/test_c02t02_posting_bundle.py.
9. Rollback: revert the bundle; everything is default-off.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5501). Matrix, flags, registry and error codes regenerate cleanly; banned_patterns scan clean. TABLE_OWNERS land with the T04/T05 migrations (their tables do not exist yet); the gate kinds are C-02-T14 (S50). Action names are two-part entity.verb (the matrix rejects three-part names), so the plan's integration.settings.* and engagement.ledger_settings.update are gl_posting_settings.* and engagement_ledger_settings.update; the plan's w9_uploaded kind is vendor_form_uploaded (C16 codes are letters and underscores only). Gates and tests run once at the S49 end pass (build first, test last).
