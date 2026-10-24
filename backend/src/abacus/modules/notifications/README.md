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

## Registering a notification kind (C16; P-01-T17)

A kind is one row of a person's feed, of one code. Adding one is a code change in the owning module plus database content; nothing in this module's code changes except the catalogue line when the kind fans out from a domain event.

1. **Register the kind** from the owning module, through `notifications.api`, at import:

   ```python
   from abacus.modules.notifications.api import NotificationKind, register_kind

   register_kind(NotificationKind("firm_export_ready", "system", "Download"))
   ```

   - `code`: snake_case, no dot (`UNDOTTED`). The dotted codes in `LEGACY_DOTTED` are SPEC-013's and are not extended.
   - `category`: the drawer tab (`approval`, `mention`, `client_activity`, `run`, `deadline`, `system`, `other`).
   - `glyph`: a name from the icon registry (F-05-T13).
   - `email_default`: whether the kind emails a person who has not chosen (most kinds: `False`).
   - `inline_actions`: only from the closed set `INLINE_ACTIONS`; an agent-originated kind (`AGENT_KINDS`) offers none (INV-1).
   - `facts` and `pending`: read-time resolvers. They read identifiers and codes only, under the reader's tenant, and must re-check walls; a row never stores text.

   Registering the same code twice with different settings is refused. Fan-out drops an unregistered kind (with a metric), so a kind that is not registered never reaches a feed.
2. **Fan it out** (when an event causes it): add one line to `CATALOGUE` in `catalogue.py`, keyed by the event type, naming the stored code, a recipient function, the subject type and payload key, and the engagement key (`None` for a firm-level kind). Add the fixed English line to `TEMPLATES` under the same key. Recipients are resolved from current memberships (`identity.api`), never an agent or the platform, and never the person who caused the event when the kind says so. A subject type that is new to the audit trail joins its owner's audit targets.
3. **Email text is content**: the `notification.<code>` email template is imported through `POST /v1/platform/email-templates/import` (staff, per environment) and published as a database row, never committed (AGENTS 16). Until a template is published for the kind, its emails settle `suppressed`.
4. **Extend the closed lists the tests pin:** `tests/unit/notifications/test_catalogue.py` (the approved kinds and a recipients test), the worker's routed events follow `CATALOGUE` by themselves, and `tests/integration/backfill/test_p01t14_notifications.py` names the kinds that email by default; `tests/contracts/c16_notifications/test_c16_kinds.py` holds the registry to the contract.
5. **Contract:** C16 v1 is frozen (`docs/contracts/notifications.md`). A new kind is additive (a new `kind` value, its facts as optional fields); a change to an existing kind's shape needs v2.

## Pausing notification email

`notifications.email` is the per-firm kill switch for the channel. Turning it off settles new deliveries and any in-flight send as `suppressed`; the in-app feed is unaffected. Procedure: `docs/runbooks/RB-31-notification-email-pause.md`.
