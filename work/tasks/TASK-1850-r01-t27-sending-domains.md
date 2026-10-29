---
id: TASK-1850
title: R-01-T27 sender domains, delivery events and the client-mail gate
spec: SPEC-345
acceptance_criteria: [AC-1, AC-3, AC-4]
risk_zone: red
status: in-review
epic: R-01
branch: s12r-r01-t27
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Brightwater Hale's domain moves from Pending DNS to Verified on the fake, a real firm's client mail
is blocked before its flip, and a bounced address is suppressed (R-01 stories 8.3, 9.2; C16 v1.1).

## Plan (red)
- Migration 0340 (on 0291; re-chain at merge): `sending_domains` (forced RLS, a transition
  trigger, one live domain per firm and per name across firms), `firm_mail_policies` (no app
  privilege; definer `client_mail_enabled()` for the app, `set_client_mail(...)` for `abacus_ops`
  only, two different people to open), `messages.from_domain`. Registry and schema_check lists.
- `communications/sending_domains.py`: create, check, revoke, list; `decide` (the one check rule);
  `sender_for` (From selection); `client_mail_open` (the gate, fail closed); the outbox subscriber
  that starts `SendingDomainVerification` (workflows.py, every 15 minutes, 72 hours, ContinueAsNew
  per day) and its activity.
- `send_templated`: the gate first (`firm_not_client_facing`), then the existing refusals; From and
  Reply-To from `sender_for`; `from_domain` recorded. Transports take `from_address`.
- `deliveries`: `message.delivery_status_changed` on delivered, bounced, complained, rejected;
  `delivery_status(message)` reads the latest event (messages stay insert-only).
- Routes: the four sending-domain routes live (C16 §2), 503 `sending_domain_unavailable`.
- Notifications `sending_domain_verified`, `sending_domain_failed` (firm and security admins).
- `abacus_tools.client_mail open|close` for the M10 flip.
- Tests: `tests/unit/communications/test_r01t27_sending_domains.py`,
  `tests/integration/test_r01t27_sending_domains.py`; the R-01-T19 and T24 send tests open their
  firm's client mail (their firms are real, so the gate now applies); the C16 stub test lists the
  four routes as built.
- Rollback: downgrade 0340; the routes go back to answering through the stub (revert the commit).

## Decisions
DEC-950 to DEC-955 (`docs/product/decision-log.md`).

## Open
- Workflow replay history for `SendingDomainVerification` v1: generate and commit during the end
  test pass (ADR-090).
- The neutral fallback From is the platform's `ses_from_address` under the firm's name, not yet
  `<firm-slug>@<neutral-mail-domain>`: P-08 exposes no slug reader to the app (DEC-950).
- Other client-facing sends outside `send_templated` (invitations, sign-in codes) are not gated
  here: they belong to their own epics (DEC-953).

## Progress log
- 2026-10-28: built, tests written (not run: end review per the session's rule).
