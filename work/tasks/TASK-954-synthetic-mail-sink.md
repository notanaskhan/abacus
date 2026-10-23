---
id: TASK-954
title: Synthetic mail sink rewrite and refusal, FakeSesTransport, mailbox readers, and their AC tests (F-04-T22, F-04-T23)
spec: SPEC-307
acceptance_criteria: [AC-5]
risk_zone: amber
status: done
epic: F-04
plan_key: F-04-T22
branch: TASK-953-notification-email
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"No synthetic-tenant email reaches a non-sink domain and mail.latest() returns the POR-01b code" (T22). "Tests prove rewrite, refusal and address-free logging for synthetic tenants on every transport" (T23).

## Plan (amber: written before the code)
- **Files:**
  - `communications/sink.py` (new): the rewrite and refusal.
  - `communications/deliveries.py`: `send_email` routes a synthetic firm's recipient first.
  - `communications/fake_ses.py` (new): `FakeSesTransport` and `FakeSesEventQueue`.
  - `communications/transport.py`: a shared mailbox writer.
  - `kernel/config.py`: `mail_sink_domain`, `mail_sink_bucket`, `mail_sink_prefix`.
  - `abacus_tools/harness/mailbox.py` (new): the local and S3 readers, `mail().latest(to)` and the CLI.
- **Migrations:** none.
- **Tests:** `tests/integration/test_synthetic_mail_sink.py`, written from F-04.22, F-04.23 and SPEC-307 AC-5 before the code (the T23 suite). It covers:
  - rewrite on `LocalMailbox`, `FakeSesTransport` and `SesTransport`;
  - look-alike domains;
  - kept sink addresses;
  - real firms untouched;
  - a configured sink;
  - refusal with no sink, logged without the address;
  - malformed addresses;
  - the fake's simulator events through the real drain;
  - `mail.latest()` returning the code;
  - the staging reader's MIME parse.
- **Rollback:** revert the commit. Synthetic firms' mail then goes where it is addressed, so revert only together with a staging sender freeze (R-8).

## Decisions
DEC-152 (the sink and fake half).

## Deferred
- The Playwright hosted sign-in that shells out to `python -m abacus_tools.harness.mailbox latest <address>` registers with F-04-T27 (the WorkOS fake), the task that has the sign-in to drive.
- The staging receipt rule and bucket are Q-01-T47's (Terraform). The reader takes them from `mail_sink_bucket` and `mail_sink_prefix`.

## Progress log
- 2026-10-23: built in one PR with P-01-T12. The suite's 39 tests and the Q-01-T46 deliveries suite pass.
