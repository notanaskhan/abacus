# C16 · Notification kinds and transactional email templates (v1)

| Field | Value |
|---|---|
| Register row | C16 in `docs/contracts/README.md` |
| Version | v1 |
| Status | frozen v1 (2026-10-23, P-01-T12; snapshot `backend/tests/contracts/c16_notifications/v1.json`). Live: the feed (P-01-T06), the preferences and the email channel (P-01-T12), the email-template half (P-01-T05) |
| Provider epic | P-01 (notifications half: AY; email-template half: N), co-provided with R-01 |
| Consumers | SHL-01 (bell), SHL-04 (drawer), SHL-03 (preferences row). Kind registrations: P-04, P-05, P-06, P-10, K-03, K-04, N-02, I-01, T-01 |
| Freeze sprint | S5 (Contract Monday, Dec 28, 2026). The freeze is recorded with P-01-T12 |
| Flags | `notifications.v2` and `notifications.email` (both default off, expire 2027-01-20) |
| Spec | `docs/plan/epics/P-01.md` §3.3, §3.4, §4.6, §7.1, §8.2 |
| ADRs | P-36 (list envelope, facts), P-35 (Undo), ADR-031 (classification), ADR-089 (flags) |

## 1. Purpose
Other modules can rely on one registration slot for notification kinds, one read API that the drawer renders without knowing any kind, per-kind preferences, and (in the email half) database-held email templates with a whitelisted renderer. Notification rows store identifiers and codes only. Everything shown is resolved at read time, so a wall, a revoked grant or a decision taken elsewhere changes what the drawer shows without rewriting rows.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| v2 list (tabs, counts, facts) | `GET /v1/notifications/feed?tab=all\|approvals\|mentions\|client_activity&cursor=&limit=30&days=30` | `OWN` (the caller's own) | every member | denied (no own notifications) |
| v1 list (kept for one release) | `GET /v1/notifications?unread=&before=&limit=` | `OWN` | every member | denied |
| Mark read | `POST /v1/notifications/{id}/read`, `POST /v1/notifications/read-all` | `OWN`. Walled ids answer 404 | every member | denied |
| Preferences | `GET /v1/me/notification-preferences`, `PUT /v1/me/notification-preferences` | `OWN`. The PUT is audited | every member | denied |
| Template import (email half) | `POST /v1/platform/email-templates/import` | `STAFF` marker, staff issuer with MFA (DEC-133; no matrix row) | platform staff | denied |

Behaviour behind `notifications.v2`: when it is off, the v2 routes answer 404. When it is on, the feed (P-01-T06) and the preferences (P-01-T12) are live. `GET` lists every registered kind with the caller's choice, or the kind's default (in the app on; email as the kind declares: `mention` on, the rest off). `PUT` saves the caller's own choices only; an unchanged choice writes nothing, and a kind turned off in the app is neither shown nor counted in the feed.

**Email channel (P-01-T12).** At fan-out, a new notification whose recipient has email on for its kind gets one `notification_deliveries` row (`UNIQUE (notification_id, channel)`):
- With `notifications.email` on, the row is `queued` and `NotificationEmail` starts once (`notification_email:<tenant>:<notification_id>`, work class `time_sensitive`). Its send activity proves the delivery from the row (still queued, the switch still on, the recipient not walled), renders the published template `notification.<kind>` with the four whitelisted values, and sends through `communications` `send_email`. On a synthetic firm the mail goes to the sink (F-04-T22), and a suppressed address is refused (Q-01-T46). The record activity settles the row as `sent` (`message_ref` is the message id, the notification's id), `suppressed` or `failed` (no published template, no address, or a send that failed).
- With the flag off (the kill switch), the row is `suppressed` and nothing is sent.

Rendering happens inside the activity, so no name, address or text enters workflow history.

## 3. Models
Code: `backend/src/abacus/modules/notifications/contract.py`.

- **`NotificationItemOut`**:
  - Internal: `id`, `kind`, `category`, `created_at`, `read`, `actor {kind: human|agent|system|policy, user_id?}`, `subject {type, id}`, `engagement_id`, `inline_actions[]`, `pending`.
  - Restricted: `facts`. They are resolved now, may hold client content, and are never logged (ADR-031). No TIN is ever a fact.
- **`NotificationFeedOut`** (internal): `items`, `next_cursor`, `counts {approvals, mentions, client_activity}`, `unread_count`.
- **`NotificationPreferenceOut` / `NotificationPreferencesIn`** (internal): `items [{kind, in_app, email}]`. They cover registered kinds that are enabled for the firm.

**Registration slot** (P-01-T06):
```
notifications.register_kind(NotificationKind(
    code, events, category, recipients, facts_resolver, pending_resolver?, inline_actions,
    glyph, email_default, actor_kind_from))
notifications.register_kind_source(code, event, recipients, subject)
```
- A code registers once; a second registration fails at startup.
- At fan-out, unregistered kinds are dropped with a metric.
- `register_kind_source` lets a later epic add a producing event to an existing kind. P-05 uses it to add `mention.created` to `mention`.

**Kind-code convention:**
- New kind codes are snake_case **with no dot**: `client_uploaded`, `mention`, `review_assigned`, `decision_assigned`, `todo_assigned`, `binder_marked_done`, `run_needs_input`.
- Event types stay dotted (`<aggregate>.<verb>`).
- `register_kind` refuses a new dotted code.
- These legacy SPEC-013 codes stay valid under the widened database CHECK (`^[a-z][a-z_]*(\.[a-z][a-z_]*)?$`, P-01-T03):
  - `support_session.*`, `budget.*`
  - `engagement.member_self_joined`, `engagement_member.added`
  - `connection.*`, `independence.requested`, `reminders.drafted`, `agent.digest`
- P-01-T03 renames three codes, with a backfill: `evidence.uploaded`→`client_uploaded`, `comment.mentioned`→`mention`, `review.assigned`→`review_assigned`.

**Categories:** `approval`, `mention`, `client_activity`, `run`, `deadline`, `system`, `other`. The tabs map to them as follows: Approvals is `pending` rows, Mentions is `mention`, and Client activity is `client_activity`.

**`pending`:** true while the row still waits on the viewer. Its kind's `pending_resolver` decides this at read time, so an upload accepted elsewhere drops out of Approvals.

**`inline_actions`:** a closed set, `accept_document`, `return_document` and `open_sign_off`. Agent-originated kinds (`run_finished`, `run_needs_input`, `proposal_routed`, `trigger_run_finished`, `template_update_available`) carry none (INV-1). A contract test enforces this (P-01-T14).

**Preference defaults:** `in_app` is true. `email` is the kind's `email_default`. Email also needs `notifications.email` to be on for the firm.

**Email templates** (P-01-T05):
- The key is `notification.<kind>`.
- The whitelisted variables are `recipient_first_name`, `kind_sentence`, `engagement_display_name` and `app_link`. An unknown variable is refused.
- No Restricted fact ever appears in an email.

**TRI (§7216):** a future tax kind declares its TRI facts and resolves them only behind C19's consent gate.

## 4. Status words
Notification rows carry no lifecycle status. Item status words inside `facts` come from `docs/product/status-vocabulary.yaml` (for example "Uploaded – needs review").

## 5. Human-only actions
- Inline Accept and Return call the existing `evidence.accept` and `evidence.reject` routes, which are human-only at the matrix and at `require_live_human`.
- Undo uses the same action and must be done by the same person, within 10 s by `kernel.clock` (P-01-T13).
- No agent-originated row offers an inline action.

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not found"}` | `notifications.v2` off (stub), or a walled or foreign notification id |
| 422 | `{"detail": "unknown_notification_kind", "facts": {"kind": "<code>", "count": n}}` | a preference names a kind that is not registered, or names one twice; nothing is saved |
| 409 | `{"detail": "proposal_changed"}` | inline Accept on a version that changed (evidence route) |
| 409 | `{"detail": "undo_window_closed"}` | Undo after 10 s or after a later decision |

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `notification_preference.changed` | `PUT /v1/me/notification-preferences`, when a choice changed | user id, count of choices changed |
| `notification_delivery.queued` / `.suppressed` | fan-out writes the email delivery row | notification id |
| `notification_delivery.sent` / `.suppressed` / `.failed` | `NotificationEmail` settles the row | notification id |
| `notification.read` (existing) | mark read | notification id |
| `email_template_version.imported` | template import (P-01-T05) | template key, version |

## 8. Example payloads
Brightwater Hale E0. Hannah Leclerc, Mon Sep 14, 9:41 AM CT.

Tab counts on SHL-04a: "All · Approvals 3 · Mentions 1 · Client activity".
```json
{"counts": {"approvals": 3, "mentions": 1, "client_activity": 0}, "unread_count": 4, "next_cursor": null}
```

Row d (live kind `client_uploaded`, category `client_activity`, pending):
```json
{"kind": "client_uploaded", "category": "client_activity", "read": false, "pending": true,
 "actor": {"kind": "human", "user_id": null},
 "subject": {"type": "evidence_version", "id": "<uuid>"},
 "facts": {"client_display_name": "Harborline Trust Company", "document_name": "certified trust report",
           "match_percent": 96, "item_status": "Uploaded – needs review", "seen_proposal": "<token>"},
 "inline_actions": ["accept_document", "return_document"]}
```

Approvals with nothing waiting (SHL-04b′): `{"items": [], "counts": {"approvals": 0, ...}}`, rendered as "No approvals waiting on you."

## 9. Consumer contract tests
`backend/tests/contracts/notifications/` (P-01-T14). It covers:
- every registered code passes the database CHECK and the undotted rule;
- no code registers twice;
- inline actions stay in the closed set;
- agent kinds offer none.

The email half's tests are P-01-T15.

## 10. Versioning
Additive changes go in place. Breaking changes ship as v2 with one sprint of overlap.

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | 2026-10-23 (P-01-T12; recorded early, before S5's Dec 28) | | 2026-10-22: stub (P-01-T01); the feed went live in P-01-T06 the same day. During the overlap the v2 list is served at `/v1/notifications/feed`, beside the v1 `GET /v1/notifications`. It moves to `GET /v1/notifications` when the v1 consumer is gone |

v1.1 (R-01-T16, 2026-10-26) is additive and lives in `email-templates.md` and `portal-settings.md`: the firm-editable template slot, `send_templated`, the POR-20 and ADM-10 routes. Nothing in this document's models changes.

## 11. Open points
- **Templates are content.** `notification.<kind>` versions come from the staff import (`POST /v1/platform/email-templates/import`), never from code. A kind without a published template gets a `failed` delivery and no email. `notification.mention` must be imported on each environment before `notifications.email` is turned on for a firm.
- **Feed path during the overlap.** The plan puts the v2 list on `GET /v1/notifications` with a `tab` parameter. To avoid a breaking change to v1's shape, the stub serves it beside v1 for one sprint, per the contract rules. Recorded here and in TASK-398.
