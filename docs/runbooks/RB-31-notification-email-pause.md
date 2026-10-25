---
id: RB-31
title: Pause notification email for a firm or every firm
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-31 · Pause notification email for a firm (or every firm)

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 to SEV2 |
| Linked from | none yet (RB-20's deliverability alarm, SLO-07, points here for the pause step) |
| SLO affected | SLO-07 (email delivery) |
| Kill switches that apply | `notifications.email` per firm (the C16 channel's kill switch); the platform outbound-email line (Q-01) for every firm |
| Rehearse by | R1 (Fri Dec 11, 2026) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Written for P-01-T17 (P-01 §8; C16, `docs/contracts/notifications.md`). Notification email is the email copy of an in-app notification; pausing it never touches the in-app feed, and never touches the client-facing sends that communications makes from its own templates (follow-ups, invitations), which have their own controls.

## 1. Recognise it
Pause notification email when any of these holds:
- a wrong or broken `notification.<kind>` template version is being sent (a firm reports it, or the staging sink shows it);
- RB-20 fires (bounce or complaint spike) and the spike is notification email;
- a kind fans out to the wrong people (a catalogue or recipient bug) and its email copy would spread it;
- a firm asks for notification email to stop while it is investigated.

Check first: `notification_deliveries` rows (channel `email`) for the firm, grouped by kind and status over the last hour (as the database owner, read-only), and the staging sink for the rendered message. If the problem is the in-app rows themselves, this runbook only stops the copies: fix the fan-out as a code change.

## 2. Contain
One firm:

```
make flag FIRM=<tenant_id> FLAG=notifications.email VALUE=false OPERATOR=<handle> REASON="RB-31: <ticket>"
```

The flag is read when a delivery row is written and again by `NotificationEmail` just before it sends, so new notifications are written `suppressed`, and a send already queued settles `suppressed` instead of sending. The cache holds a flag value for at most its cache window (`kernel.flags.CACHE_SECONDS`): wait that long before declaring it contained.

Every firm: use the platform outbound-email line (Q-01, the deployment's email kill switch), not a loop over firms; it stops all outbound email, client-facing sends included, so say so in the incident channel.

## 3. Preserve
Capture before changing anything: the delivery rows (ids, kinds, statuses, timestamps), the template version ids that were sent (`email_template_versions`), the `NotificationEmail` workflow ids and their histories. Never copy a rendered email body or a recipient address into a ticket; refer to rows by id.

## 4. Assess
- Which firms and which kinds; how many deliveries were `sent` in the window.
- Whether any sent body carried client content it should not have (the body check refuses TINs, account numbers and tax amounts; a template bug can still name an engagement). If client content reached the wrong person, this is RB-08's question: go there.

## 5. Notify
Tell the firm's admins in-app (a support note) that notification email is paused and in-app notifications continue. If client content reached a wrong recipient, RB-27 sets the 72-hour clock.

## 6. Recover
1. Fix the cause: import a corrected `notification.<kind>` version (`POST /v1/platform/email-templates/import`, staff; content, never committed) or merge the code fix.
2. Check on staging that the corrected email renders and reaches the sink.
3. Turn the channel back on: `make flag FIRM=<tenant_id> FLAG=notifications.email VALUE=true OPERATOR=<handle> REASON="RB-31: resolved <ticket>"`.
4. Deliveries settled `suppressed` while paused are not re-sent: a notification's email is a convenience copy and the in-app row stands. Say so in the review.

## 7. Verify
A new notification of a kind that emails creates a `queued` row that settles `sent` (or `suppressed` by the sink rule on staging), and the audit trail shows the two `feature_flag` changes with the operator and reason.

## 8. Review
Open the blameless review (ADR-097). If a template slipped through, add a template check or a staging smoke step; if fan-out was wrong, add the recipient case to `tests/unit/notifications/test_catalogue.py`.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
