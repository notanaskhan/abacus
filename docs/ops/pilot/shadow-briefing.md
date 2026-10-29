---
version: shadow-briefing v1
updated: 2026-10-30
---
# The shadow rules: what a firm agrees to for its first window (PW1)

**Version: shadow-briefing v1.** AY walks each PW1 firm admin through this page before go-live
(Q-04-T022), after the AI disclosure briefing (F-09-T127). The admin acknowledges it **in writing**
(a reply to the briefing email is enough); the reply goes in the vault and the dossier records the
date, this version and the vault entry, never the person's name (`docs/ops/go-live/<pilot-code>.md`,
"Shadow rules acknowledged"). A new version of this page means a new acknowledgement.

## 1. What shadow means (PW1, Jun 1 – Jul 12, 2027)

1. **Staff only.** Only the firm's own staff use Accrued, on 1–3 engagements per audit partner.
   No client, third party or portal user is invited; the client portal stays off for the firm.
2. **No client email.** Accrued sends no email to any client or third party. Staff notifications
   come from Accrued's verified platform domain; the firm's own sender domain is set up and
   verified ahead of time, and stays unused until the client-facing window (M10, Tue Jul 13, 2027).
3. **Nothing client-facing.** No request, reminder, portal page, signature envelope or document
   reaches anyone outside the firm. Client-facing switches are off and the go-live check proves it
   (`communications.no_client_facing`).
4. **Agents in shadow.** Each assistant the firm opted in to runs on the firm's data and is
   recorded, but **nothing it produces is shown** to anyone: screens behave as if it were off
   (SPEC-036). Its outputs are scored against the firm's own decisions. Promoting an assistant to
   live is a later, separate decision per assistant, with the firm.
5. **The firm's tools stay the system of record.** Staff load the firm's PBC lists, file documents
   the firm received through its existing channels, and use screening and matching. Workpapers,
   sign-offs and reports stay where they are today; nothing posts to or writes into the firm's
   systems (no write capability is enabled in shadow).
6. **Leaving is always possible.** A rollback hands the firm its engagements as files and switches
   everything off within an hour (`docs/runbooks/firm-rollback.md`).

## 2. What the firm admin acknowledges

> I have read the shadow rules (shadow-briefing v1). For our first window my firm's staff alone
> use Accrued; no client email is sent and nothing reaches anyone outside the firm; the assistants
> we opted in to run in shadow and show nothing; our existing tools remain our system of record.

## 3. For AY: the dossier's AY sections

Fill the by-hand rows of Communications, Content and Integrations in the firm's dossier with this
evidence (a screen state or a CLI line; never a screenshot of client data):

| Dossier row | Evidence | Where |
|---|---|---|
| communications-1 · no client-facing email; staff email from the platform domain | `communications.no_client_facing` pass in the go-live check; the platform domain's status | `make go-live-check`; ADM-10 |
| communications-2 · the firm's sender domain verified ahead of R3 | ADM-10 **f** (verified, published), date | ADM-10 |
| content-1 · clients, PBC templates and email templates through the firm's screens | CLI-06 **g** import id and counts; KNW-01 version id; POR-20 **l** template keys published | the firm's screens; `pilot-onboarding.md` §4–6 timings |
| integrations-1 · only built connectors Available; POR-16 "Export instead" | POR-16 states seen as the firm's client admin would | POR-16 |
| integrations-2 · production keys and approvals for this firm's connectors; reconnect tested | the connector's registration and a reconnect run (A-02-T33 for the live ledger) | vault; POR-16 **c**, **d** |
| Shadow rules acknowledged | the acknowledgement reply's date and vault entry, this version | vault |
