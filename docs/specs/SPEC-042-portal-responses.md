---
id: SPEC-042
title: "Client portal: the client's words for requests, \"This doesn't apply\" with a reason, and \"Mark as done\""
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-004, ADR-005, ADR-111]
related_specs: [SPEC-020, SPEC-031]
created: 2026-10-20
updated: 2026-10-20
---

## 1. Summary
This follows the plan's POR-03 and POR-04.
- **Client words.** The client sees their own words for a request: **To do**, **Done**, **Returned** and **Doesn't apply**. They never see the firm's internal states.
- **This doesn't apply.** The client can say a request doesn't apply, with a reason ("Not applicable this year", "Already sent another way", "I don't have this") and an optional note. They can undo it.
- **Mark as done.** The client's administrator can mark their list done when every request is done or doesn't apply.

The firm sees the response on the request ("Client: doesn't apply — reason") and "Marked done by {name}". A response never changes the request's status: the firm still decides (ADR-005).

## 2. Acceptance criteria
- **AC-1** A client admin (on a client-visible item) or the assigned contributor responds that an item doesn't apply, with one of the three reasons and an optional note (up to 500 characters). It's recorded with who and when; an audit event is written.
- **AC-2** They can withdraw the response. The newest record counts, and nothing is deleted (insert-only).
- **AC-3** Firm roles and clients read the responses through the same visibility as the items (`request_item.read`, `visible_items`).
- **AC-4** The client admin marks the list done only when every item they can see is done (uploaded or provided) or doesn't apply; otherwise `list_not_done` (409). The firm sees who marked it and when.
- **AC-5** The portal shows the client words, the reason sheet, the "Doesn't apply" state with Undo, and a "Mark as done" bar showing "n of m done". The firm's Requests list shows the client's response on the row and "Marked done by {name}" in its header.

## 3. Data
- `client_item_responses` (insert-only): `tenant_id`, `engagement_id`, `request_item_id`, `kind` (`not_applicable` | `withdrawn`), `reason` (`not_this_year` | `sent_another_way` | `dont_have`, null when withdrawn), `note`, `by_user`, `created_at`.
- `client_list_done` (insert-only): `tenant_id`, `engagement_id`, `by_user`, `created_at`.

## 4. Permissions
- `client_item.respond`: client_admin: client_visible_only; client_contributor: assigned_only.
- `client_list.mark_done`: client_admin: allow.
