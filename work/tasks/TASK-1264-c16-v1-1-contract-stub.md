---
id: TASK-1264
title: C16 v1.1 contract stub for the POR-20 and ADM-10 family - templates, sending domains, follow-up policy, portal settings; docs/contracts/email-templates.md and portal-settings.md (R-01-T16)
spec: SPEC-345
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: red
status: in-review
epic: R-01
plan_key: R-01-T16
branch: s9a-contract-stubs
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The stub merges with every flag off and the consumers named in the contract doc" (R-01-T16).
`notifications.md` stays C16 v1 (frozen, P-01-T12); v1.1 is additive in two new docs.

## Plan (red zone: contract)
- **Slot** `communications/template_registry.py` (new): `register_email_template(key, audience,
  variables, cta_targets, used_by, firm_editable)`, the variable whitelist with a sensitivity
  class per variable (none an amount, account number or TIN), `SendRefusal` (`template_missing`,
  `template_lint_failed`, `firm_not_client_facing`, `suppressed`), the lint finding shape and the
  `send_templated` signature (raises `NotImplementedYet` until R-01-T19). Exported from
  `communications/api.py`. R-01's six keys are registered by T19, not here (content is T19's).
- **Routes** `communications/templates_contract.py` (new) behind `portal.settings_editor` for the
  editor (list, read, draft save/discard, publish, preview, test-send, import) and
  `communications.firm_sender_domain` for sending domains; `GET /v1/firm/follow-up-policy`
  behind `portal.settings_editor`. Portal settings `portal/settings_contract.py` (new): read,
  draft save/discard, publish, logo, preview. 404 off, 501 on.
- **Flags**: `portal.settings_editor` (portal.yaml), `communications.firm_sender_domain` and
  `follow_ups.scheduled_send` (new communications.yaml).
- **Matrix**: `email_template.{read,edit,test_send,publish,import}`,
  `sending_domain.{read,manage}` (communications.yaml); `portal_settings.{read,manage}` and
  `portal.preview` (portal.yaml; DEC-139 spells `portal.settings.*` with one dot). Agent and
  system denied on every one.
- **Docs**: `docs/contracts/email-templates.md`, `docs/contracts/portal-settings.md`, register
  rows; `notifications.md` §10 points at v1.1.
- **Tests**: `backend/tests/contracts/c16_notifications/test_c16_v1_1_stub.py` (provider).
- **Rollback**: revert and `make regenerate`; no migration.

## Progress log
- 2026-10-26: built. SPEC-345 written (the reserved second SPEC number) because SPEC-323 has
  no C16 ACs. `tests/contracts/c16_notifications` 121 passed, 1 xfailed (pre-existing, #380);
  C16 v1's frozen snapshot unchanged. App gates (import, preview, check and logo create nothing;
  test send 202; publish, domain and settings publish 201) and the status-vocabulary suite
  (`SendingDomainOut.status` recorded until R-01-T28) pass. DEC-378.
- Not here: the six keys' registrations and content (T19, T22); fresh-MFA register entries for
  the new mfa actions (the register's groups have no "client mail" group; add with T19 or T26);
  `test_agent_never.py` rows (R-01-T20, T30).
- 2026-10-26 (security review, DEC-379): fix round on the same branch; see DEC-379 for this task's part (H1 preview scoping, M1 send_templated signature, M2 value lint, M3 connection.disconnect, M4 section requester, L1 test-send conditions, L4 support contact).
