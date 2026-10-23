# notifications

In-app notifications (SPEC-013). Modules publish domain events. This module subscribes to the catalogued ones (`catalogue.py`) and stores one notification per recipient: identifiers and a kind, never text. The SPA renders text from `TEMPLATES`.

**Catalogue:**

| Event | Notifies |
|---|---|
| `support_session.requested`, `support_session.emergency_approved` | firm admins |
| `budget.soft_crossed`, `budget.anomaly` | firm admins, plus the engagement's partner and managers |
| `engagement.member_self_joined` | the engagement team, except the admin who joined |
| `review.assigned` | the assignee |
| `comment.mentioned` | the people mentioned, firm or client (SPEC-032) |

**Delivery:** at least once through the relay, idempotent on (event, recipient).

**Reading:** `GET /v1/notifications`, `POST /v1/notifications/{id}/read` and `POST /v1/notifications/read-all`, with the route marker `OWN`.
- Each user sees only their own.
- Walls and need-to-know are re-checked at read time.
- Support contexts are refused.

**Preferences (P-01-T12, C16):** `GET` and `PUT /v1/me/notification-preferences` (`OWN`, behind `notifications.v2`).
- Every registered kind, with the person's own choice or the kind's default.
- A kind turned off in the app is not shown in the feed. An unknown or repeated kind answers 422 `unknown_notification_kind`.
- A change is audited (`notification_preference.changed`).

**Email (P-01-T12, `email.py`):**
- A new notification whose recipient wants email for its kind gets one delivery row.
  - `queued` while `notifications.email` (the kill switch) is on. Off, it is `suppressed`.
- `NotificationEmail` (`workflows.py`; `time_sensitive`; one per notification) sends it through `communications.api.send_notification_email`, which goes through `send_email`, so the sink rule and suppression apply. It then settles the row: `sent`, `suppressed` or `failed`.
- Templates are the published `notification.<kind>` versions (database content).
- Replay histories: `tests/workflows/histories/notification-email-v*.json`.

**Retention:** a daily purge removes notifications older than 180 days.
