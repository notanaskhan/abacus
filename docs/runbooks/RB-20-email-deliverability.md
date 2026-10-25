---
id: RB-20
title: Email deliverability incident
owner: builder
alarms: [SLO-07, ses-bounce-rate, ses-complaint-rate]
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-20 · Email deliverability incident

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 to SEV2 |
| Linked from | SLO-07, SES bounce rate over 2%, complaint rate over 0.05% |
| SLO affected | SLO-07 |
| Kill switches that apply | `notifications.email` per firm (RB-31); the platform email pause (Q-01-T36, not built yet); SES configuration-set sending pause |
| Rehearse by | R1 (Fri Dec 11, 2026) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

SES sends through the environment's configuration set; delivery events reach SQS and the one-minute drain records them in `message_deliveries`, suppressing an address hash after a permanent bounce or a complaint (Q-01-T46). A synthetic firm's mail goes only to the staging sink.

## 1. Recognise it
- The bounce or complaint rate alarm, or SLO-07's stalled queue.
- Check `message_deliveries` by event over the last hour (identifiers only), and whether one firm or one template dominates.

## 2. Contain
- One firm or one kind of notification: RB-31.
- Everything: pause sending on the SES configuration set (`aws sesv2 put-configuration-set-sending-options --configuration-set-name <set> --no-sending-enabled`); the platform email pause replaces this once Q-01-T36 lands.

## 3. Preserve
The delivery events (ids, events, bounce kinds), the SES reputation dashboard values, the template versions sent. Never recipient addresses in a ticket.

## 4. Assess
A bad list (a firm imported stale contacts), a broken sender domain (DKIM, custom MAIL FROM: the SES identity port), or content flagged as spam.

## 5. Notify
The affected firm's admins in-app. No status page unless all sending is paused for over an hour.

## 6. Recover
Fix the cause (DNS records through the firm's sender-domain screen, the template, the list), then re-enable sending and watch the rates for an hour.

## 7. Verify
Bounce and complaint rates back under the thresholds for 24 hours; SLO-07's queue drains.

## 8. Review
Typical actions: a pre-send check, an alarm earlier on a firm's bounce rate.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
