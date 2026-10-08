# notifications

In-app notifications (SPEC-013). Modules publish domain events. This module subscribes to the catalogued ones (`catalogue.py`) and stores one notification per recipient: identifiers and a kind, never text. The SPA renders text from `TEMPLATES`.

**Catalogue:**

| Event | Notifies |
|---|---|
| `support_session.requested`, `support_session.emergency_approved` | firm admins |
| `budget.soft_crossed`, `budget.anomaly` | firm admins, plus the engagement's partner and managers |
| `engagement.member_self_joined` | the engagement team, except the admin who joined |
| `review.assigned` | the assignee |

**Delivery:** at least once through the relay, idempotent on (event, recipient).

**Reading:** `GET /v1/notifications`, `POST /v1/notifications/{id}/read` and `POST /v1/notifications/read-all`, with the route marker `OWN`.
- Each user sees only their own.
- Walls and need-to-know are re-checked at read time.
- Support contexts are refused.

**Retention:** a daily purge removes notifications older than 180 days.
