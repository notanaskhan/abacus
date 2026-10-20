---
id: SPEC-302
title: "Command palette (SHL-02): ⌘K jumps to engagements, request items, findings, engagement tabs and pages, with walls applied to every result"
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-020, ADR-027]
related_specs: [SPEC-002, SPEC-020]
created: 2026-10-20
updated: 2026-10-20
---

## 1. Summary
The plan's SHL-02 command palette (overlay O5), first slice: no agent mode, to-dos or saved prompts.
- **Opening it.** ⌘K or Ctrl+K anywhere in the firm app, or the toolbar's Search button, opens a 640-wide palette.
- **With no query.** It shows the recent engagements (stored in this browser only), the current engagement's tabs, and the pages.
- **With a query.** It shows matching engagements, request items, findings, tabs and pages.

## 2. Acceptance criteria
- **AC-1** Engagements are filtered in the browser, from the engagements the caller can already list. A query matches when every word appears in the client, entity or engagement name, ignoring case. When nothing matches, the palette says so.
- **AC-2** Request items and findings come from the server:
  - `GET /v1/firm/search/request-items?q=` and `GET /v1/firm/search/findings?q=`;
  - only after at least 2 characters, at most 8 results each, newest first;
  - through `visible_items()` / `visible()`, so walls, independence and client-visibility apply;
  - `%`, `_` and `\` in the query are taken literally.
- **AC-3** Keys: ↑ and ↓ move, Enter opens, Escape closes.
  - A request item opens its item page.
  - A finding opens its engagement's Findings tab.
  - An engagement opens its overview and is remembered as recent.
- **AC-4** "Open notifications" opens the notifications panel. Firm settings is listed only for firm admins.

## 3. Out of scope
The `>` agent mode, Create actions, to-dos, saved prompts, clients and files as groups (no clients index yet), and wall-hidden counts (SPEC-002 AC-4 keeps walled engagements invisible).
