---
id: RB-96
title: "Support panel and system status (SHL-05): chat hours, articles, status components, support sessions"
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2028-11-14
---
# RB-96 · Support panel and system status

| Field | Value |
|---|---|
| Owner | builder (AY is the partner-facing support owner, Q-04) |
| Severity range | SEV4 (an article is wrong) to SEV2 (status shows Operational during a firm-affecting incident) |
| Source | G-04-T22 (TASK-8759); G-04 §3; SHL-05 a–f, d′; `support.panel_v2` |

## What firm users see
SHL-05: Chat (online with the 7-day median reply time, or offline with the next reply time), Help articles (structured blocks only), System status (components and the firm's data region). Chat accepts no attachments; there is no bot persona.

## Content is database rows, not deploys
Support hours, help articles, status components and regions are platform content published from the console (two-person, RB-95). Changing them never needs a deploy.

## During an incident
1. Set the affected component's status (for example "CCH Axcess Tax export · Needs attention · Delays up to 15 min since 8:40 AM CT") in the console; SHL-05 e reads it on the next load.
2. Link the incident and update every 30 minutes until resolved; clear it to Operational only after verification.
3. If chat is overwhelmed, set the hours to offline with an honest reply time; never leave "Online" up unanswered.

## Support sessions
Requested from the console, approved only by the firm (RB-12 section "Firm-content support sessions after G-04"). Support works inside the granted scope only and ends the session when done.

## Rollback
Turn `support.panel_v2` off for a firm: SHL-05 renders P-01's interim frame; chat, help and status routes answer 404 for that firm.

## Rehearsal log
| Date | Where | Who | Result |
|---|---|---|---|
| — | staging | — | not yet rehearsed: needs `support.panel_v2` on for a staging tenant |
