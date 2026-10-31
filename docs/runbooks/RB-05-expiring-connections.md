---
id: RB-05
title: Expiring-connections wave
owner: builder
owning_epic: A-02
alarms: [SLO-09]
last_rehearsed: never
rehearse_by: 2027-01-08
---
# RB-05 · Expiring-connections wave

| Field | Value |
|---|---|
| Owner | builder (written by A-02, A-02-T39) |
| Severity range | SEV3 |
| Linked from | SLO-09 |
| SLO affected | SLO-09 |
| Kill switches that apply | `connections.portal_v2` per firm (POR-16 and reconnect requests; off: 404, the legacy panel stays); `retrieval.auto` per firm |
| Rehearse by | the first live connector (once on staging, A-02-T39's acceptance) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

A wave is many connections losing their grant at once: a provider's token lifetime ending for connections made together, a provider-side revocation, or an app registration change. Only the client can fix it, by signing in again on POR-16; the firm asks them through a reconnect request, mailed from the firm's **Reconnect request** template (`reconnect_request`, database content on POR-20, R-01). Nothing is written to a client's system and nothing a firm already received is lost.

## 1. Recognise it
- After the daily health pass (`connection_health:platform`), many connections are `needs_attention` with a reauth reason (`token_expired`, `invalid_grant`), which C2 and POR-16 show as **Needs reauth**; leads get `connection_needs_reauth` notifications, once per connection.
- Seven days ahead, `connection_reauth_due` notifications for connections whose `reauth_due_at` is near: a wave you can get ahead of.
- SLO-09 burns for the affected firms; on-demand pulls answer 409 `connection_needs_reauth`.
- Not this scenario: a provider outage (non-reauth codes, RB-04).

## 2. Contain
Nothing to stop: pulls already refuse a connection that needs reauth, and retries are refused for reauth reasons until the client signs in. If the wave comes from an app registration change on our side (a rotated client secret, a changed redirect URI), fix the registration first (`settings.qbo_client_id` and secret per environment), or every reconnect will fail too.

## 3. Preserve
The health pass's `connection.health_checked` audit rows (reason codes), the list of affected connections (ids, entities, firms; no tokens), and the provider's notice if it announced the change.

## 4. Assess
- How many connections, which firms and entities, which have active closes or engagements in their freshness window.
- Whether each firm has published its **Reconnect request** template (`reconnect_request`); without a published version every send is recorded `blocked` (fail closed), never sent from a constant.
- Whether the firm has client mail on (`firm_not_client_facing` refuses sends before the firm's M10 flip).

## 5. Notify
1. The firm, not us, asks its clients: on AUD-06 a lead presses **Ask client to reconnect** per connection (`connection.reconnect_request`, one open request per connection; a second ask answers the open one and sends nothing).
2. Tell affected firms through the support channel with the counts and the AUD-06 path; offer *Export instead* (ADR-108) for anything due before the client can sign in.
3. No status page entry unless the cause is ours (an app registration change): then SEV3, component "Ledger sync".

## 6. Recover
1. Each client signs in again from the email's link or POR-16 (**Reconnect**): the connection is re-authorised in place (`connection.reauthorized`), its open reconnect request is fulfilled, and pulls resume.
2. A request whose email never went out (blocked or failed) can be asked again once the template is published; it sends once more in the next numbered slot, never twice.
3. The next health pass confirms the rest; connections still needing reauth after a week get a second ask from the lead.

## 7. Verify
The affected connections read **Connected**; `needs_attention` with reauth reasons is back to its usual level; SLO-09 recovers for the firms; no reconnect request stays open without a sent email.

## 8. Review
Typical actions: earlier `reauth_due` notices for the provider's token lifetime, a per-entity cooldown across feeds (DEC-611's follow-up), a template check before the wave (the firm's POR-20 shows the key unpublished).

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
