---
id: SPEC-013
title: In-app notifications
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-024, ADR-028, ADR-018, ADR-031, ADR-032, ADR-102, ADR-106]
related_specs: [SPEC-002, SPEC-007, SPEC-012]
created: 2026-10-08
updated: 2026-10-08
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
A notification (glossary: an alert to a user inside the platform) is one platform primitive for telling people things, with the Collaboration layer of Phase 1 §5.3 in mind:
- **How they're made:** modules publish domain events. The notifications module turns a fixed catalogue of them into per-recipient notifications.
- **What they contain:** identifiers and a kind; the text comes from code templates.
- **Who sees them:** each recipient sees only their own, and walls apply when they are read.
- **What's left for later:** email delivery (needs SES, TASK-014) and a bell in the SPA.

## 2. Problem and context
Several finished features need to tell someone something, and today they can only log it:
- **Break-glass (SPEC-012):** firms must be told about emergency sessions.
- **Budgets (SPEC-007):** soft limits crossed and spend anomalies.
- **Self-join (ADR-024):** a firm admin joining an engagement must notify the team. The matrix carries `notify: engagement_team`, and `authorise` refuses it until notifications exist.

Later increments (invitations, follow-ups, review assignment) need the same path.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Modules | Publish domain events (identifiers only) |
| The notifications module | Resolves recipients and stores notifications |
| Firm users | Read their own notifications and mark them read |

## 4. Goals and non-goals
**Goals**
- **The catalogue (Q1):** a fixed list of notification kinds, each mapping one domain event to its recipients and a template. In v1:
  - `support_session.requested` and `support_session.emergency_approved`: the firm's admins;
  - `budget.soft_crossed` and `budget.anomaly`: the firm's admins, and for an engagement also its partner and managers;
  - `engagement.member_self_joined`: the engagement team (ADR-024);
  - `review.assigned`: the assignee (the existing review assignment).
- **Delivery:** at least once through the outbox relay, deduplicated per event and recipient.
- **Reading:** a recipient lists their own notifications, newest first (unread first, optionally), sees the unread count, and marks one or all as read.
- **Walls and need-to-know:** a notification about an engagement is shown only while the recipient may still see that engagement's metadata (`visible(engagement.read_metadata)`), so walls added later hide it.
- **The self-join obligation:** `notify: engagement_team` becomes satisfiable. `authorise` allows the action and the service publishes the event in the same unit of work.
- **Retention:** notifications older than 180 days are purged by a daily background job (Q4).

**Non-goals**
- Email, push and other channels, and notification preferences (Q2).
- Client users' notifications (client portal, increment 2).
- A SPA bell and notification centre (a separate UI task).
- Free-text notifications from people.

## 5. User stories and acceptance criteria
### Story 1: Things that matter reach the right people
- **AC-1** Given a catalogued event committed by its module, then within a minute each resolved recipient has exactly one notification for it, even if the event is relayed more than once. The notification holds:
  - its kind;
  - the identifiers needed to link to the subject (engagement, session, review item);
  - the event's ID and the created time;
  - no free text and no client content.
- **AC-2** Given the recipient rules (Q1), then recipients are resolved when the notification is made, from current memberships and engagement roles. Nobody outside the firm, no client user, no agent and no system actor is a recipient.
- **AC-3** Given an event outside the catalogue, then no notification is made.

### Story 2: Each person sees their own, and nothing they shouldn't
- **AC-4** Given a user, when they list notifications, then they see only their own in their active firm, with the unread count. Another user's notifications are never returned, even by ID (404).
- **AC-5** Given a notification about an engagement the user may no longer see (walled after the fact, or removed from the team), then it is not listed and not counted.
- **AC-6** Given a user, when they mark a notification read (or all read), then `read_at` is set once. Notifications are otherwise immutable. Reading is not audited, because it is the user's own state.
- **AC-7** Given a notification, then its display text comes from the kind's template filled with identifiers and names the user can already see. The API returns the kind and references, and the SPA renders the text.

### Story 3: Obligations become real
- **AC-8** Given a firm admin self-joins an engagement (`engagement.self_join`, `notify: engagement_team`), then the join is allowed, and in the same unit of work the event is emitted. Every engagement team member is notified (AC-1). If the event can't be emitted, nothing is committed.
- **AC-9** Given a support session requested or emergency-approved (SPEC-012), or a budget soft limit crossed or an anomaly flagged (SPEC-007), then the firm's admins (and, for an engagement, its partner and managers) are notified.

### Story 4: It doesn't pile up
- **AC-10** Given notifications older than 180 days, when the daily purge runs, then they are deleted, and the count is logged.

## 6. Behaviour and flows
1. **Publish:** a module emits a domain event in its unit of work. Where only a log exists today (budgets, break-glass), it now also emits an event. The gateway records budget events through the kernel outbox.
2. **Relay:** the outbox relay delivers each event to the notifications subscriber.
3. **Resolve:** the subscriber looks up the catalogue entry, resolves recipients through the identity and engagements APIs, and inserts the notifications. A unique key on (event, recipient) makes it idempotent.
4. **Read:** routes list and mark the user's own notifications, filtered by `visible()` for engagement-scoped ones.

## 7. Domain and data changes
- **`notifications`** (tenant-scoped, forced RLS):
  - columns: `id`, `tenant_id`, `recipient_user_id`, `kind`, `event_id` (unique with the recipient), `engagement_id` (nullable), `subject_type`, `subject_id`, `created_at`, `read_at`;
  - the app may insert, and update `read_at` only;
  - index on (`tenant_id`, `recipient_user_id`, `created_at`).
- **New domain events** where only logs exist today:
  - `SupportSessionRequested` and `SupportSessionEmergencyApproved` (identity);
  - `BudgetSoftCrossed` and `BudgetAnomaly` (ai_gateway, through the kernel outbox);
  - `EngagementMemberSelfJoined` (identity or engagements, wherever self-join lives).

## 8. Interfaces
| Interface | Purpose |
|---|---|
| `GET /v1/notifications?unread=true&limit=…&before=…` | The user's own list and unread count (AC-4, AC-5) |
| `POST /v1/notifications/{id}/read` and `POST /v1/notifications/read-all` | Mark read (AC-6) |
| The catalogue (`notifications/catalogue.py`) | Kind → event, recipients and template (AC-1 to AC-3) |
| The relay subscriptions | Event → notification |

## 9. Authorisation and tenancy
- **Own rows only (Q3):** reading and marking notifications acts on the caller's own rows. These routes use the route marker `OWN`: any active member of the tenant, with the query filtered to `recipient_user_id = ctx.user_id` plus RLS. They need no matrix action, so engagement-only users (who hold no firm role) can use them.
- **Engagement-scoped notifications** are additionally filtered with `visible(ctx, "engagement.read_metadata", engagement_id)`.
- **The matrix:** `notify: engagement_team` on `engagement.self_join` becomes allowed once the obligation is implemented (a protected change).

## 10. AI behaviour
None. Agents never receive notifications or trigger them directly.

## 11. Integrations
None in v1. Email arrives with SES (TASK-014), using the same catalogue.

## 12. Edge cases and failure modes
- **Relay redelivery:** the unique (event, recipient) key makes it a no-op.
- **A recipient leaves the firm:** their notifications stay but are unreachable, since they have no membership. The purge removes them in time.
- **A large firm:** recipient sets are bounded (admins, one engagement team), so there is no fan-out problem.
- **A subscriber failure:** the relay retries and eventually parks the event, as for any subscriber.

## 13. Security and privacy
- **No content:** notifications carry identifiers and kinds only (classified internal). Text is rendered from templates with names the viewer can already see.
- **Read-time checks:** walls and need-to-know are re-checked when notifications are read.
- **Per user:** a user can never read or mark another user's notifications.

## 14. Audit trail and evidence integrity
Producing a notification isn't audited (its event's action already is). Marking read isn't audited (AC-6). Purges log counts.

## 15. Observability
- **Metrics:** notifications created by kind, delivery lag (event to notification), and purge counts.
- **Logs:** identifiers only.

## 16. Performance and scale
One insert per recipient per event. The list query is indexed by recipient and time, with keyset pagination (`before`).

## 17. UX
API only. The SPA bell and centre are a separate task.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-3 | integration | Each catalogued event produces one notification per recipient; redelivery is idempotent; uncatalogued events are ignored |
| AC-4 to AC-6 | integration | Own only; 404 for others; walls hide; read once |
| AC-7 | unit | Templates render from identifiers |
| AC-8, AC-9 | integration | Self-join allowed and notifies the team; break-glass and budget events notify admins |
| AC-10 | integration | The purge |

## 19. Rollout
The migration is additive. Self-join becomes possible for firm admins (it is refused today), which is a protected matrix change.

## 20. Open questions
None. Answered by the founder on 2026-10-08 (all recommendations):
- [x] **Q1: the v1 catalogue.** *Recommendation:* the six kinds in §4, with recipients as listed. Later kinds are added with their increments (invitations, follow-ups, retrieval failures).
- [x] **Q2: channels.** *Recommendation:* in-app only in v1, with no preferences. Email, through the communications module's transport and the same catalogue, comes with SES in TASK-014.
- [x] **Q3: authorising own-notification routes.** *Recommendation:* a route marker `OWN` (an authenticated member acting only on their own rows, enforced by the query and RLS), so engagement-only users aren't blocked by the firm-level read limitation. The alternative is to fix firm-level reads for engagement roles first, which is a broader authz change.
- [x] **Q4: retention.** *Recommendation:* 180 days, purged daily by a background task beside the anomaly job. Notifications aren't evidence, so ADR-032's minimums don't apply.
- [x] **Q5: owner module.** *Recommendation:* a new `notifications` module. That means amending ADR-101's module map, a small protected docs change. The alternative is putting it inside `communications`, which is about outbound messages to clients under the scope checker, a different trust boundary.

## 21. Future / explicitly deferred
- Email and digest channels, and user preferences.
- The SPA bell and notification centre.
- Client-user notifications.
- Real-time push (websocket or SSE).
