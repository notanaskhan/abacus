---
id: SPEC-031
title: "The client hub: what's needed and why, your part, and the history of every send-back"
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-004, ADR-005, ADR-027, ADR-050, ADR-052, ADR-111]
related_specs: [SPEC-008, SPEC-015, SPEC-020, SPEC-022, SPEC-023, SPEC-027, SPEC-028, SPEC-029]
created: 2026-10-12
updated: 2026-10-12
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Clients see each request the way a good audit senior would explain it: **what's needed, why, and what good looks like**, with its due date, who's on it and where it stands. Items the platform already has from the ledger are marked **provided**, so nobody uploads them. A bank statement request that's partly met names **only the gap** ("we have accounts ending 2290 and 8812; we still need 4471"). The client home shows **your part**: what's left, what blocks fieldwork, and roughly how long it will take. Every upload keeps its **history**, with the **reason for every send-back**.

This is Track A3 of the Act 2 plan. No AI writes anything a client reads (ADR-111): every word is the firm's, a fixed template, or computed by code.

## 2. Problem and context
- A client sees a request's description, area, status and (SPEC-027) due date. They don't see why it's asked or what a good answer looks like, so they guess, and the firm sends things back.
- Items met by retrieval or an import (SPEC-022, SPEC-028) look like any other "received" item; nothing says "you don't need to do anything".
- A "bank statements for all accounts" request is either open or received; nothing says which accounts are still missing, though the trial balance (cash accounts) and SPEC-029's extraction (each statement's last four digits) hold the answer.
- The client home lists engagements, nothing about the work left.
- A send-back moves the item to "needs revision" with a reason code and note (SPEC-004); the client sees the status, not the reason.
- Methodology templates (SPEC-008) carry a description, area and tier per item; nothing else.

## 3. Actors
| Actor | Role here |
|---|---|
| Client admin, client contributor | Read requests with their why and what good looks like; see their part; see history and send-back reasons; upload or replace |
| Engagement partner, manager, senior | Write or edit why, what good looks like, whether an item blocks fieldwork and its effort; write the send-back note the client will see |
| The platform (code) | Fills defaults from templates or by document kind; marks items provided; computes the bank statement gap; sums the client's part |

## 4. Goals and non-goals
**Goals**
1. **Request detail for clients**, on each request in the client's engagement page:
   - what's needed (the description), **why** and **what good looks like**, due date, assignee and status;
   - **why** and **what good looks like** are firm-written text (up to 1,000 characters each) on the request item; they default from the methodology template item, or, without one, from fixed copy per document kind (SPEC-029: bank statement, AR aging, AP aging, schedule) (Q1); partner, manager and senior edit them per engagement.
2. **Provided:** an item fulfilled by a retrieval or an import says "Provided from your accounting system on {date}" (or "from your export of {date}", SPEC-028) and asks nothing of the client.
3. **The gap, for bank statements** (code, ADR-050): for a `bank_statement` item, the cash accounts in the engagement's year-end trial balance (as SPEC-029's cross-check finds them) against the last four digits of the statements uploaded to the item; the client sees "We have statements for accounts ending 2290 and 8812; we still need 4471", and the item stays open until none is missing. Other items: the firm may write a **still needed** note the client sees (Q2).
4. **Your part** on the client home, per engagement: items left for this person (client-visible, open or needing revision, assigned to them, or unassigned for client admins), how many **block fieldwork**, and an **estimate** of the effort, for example "6 left · 2 block fieldwork · about 1½ hours".
   - `blocks_fieldwork` (yes or no) and `effort` (small, medium, large: 15, 45 or 120 minutes, Q3) are set per item by the firm, defaulting from the template or by document kind.
5. **History and send-back reasons:** on each request, the client sees every version they're allowed to see, newest first, with who added it, when, and its outcome: in review, accepted, or **sent back with the reason** (the reason code's label and the reviewer's note) (Q4). Rejections stay firm-only.
6. **Templates:** methodology template items gain optional "Why", "What good looks like", "Blocks fieldwork" and "Effort" columns in the workbook (SPEC-008), carried to engagements when the methodology is applied and on roll-forward (SPEC-025).
7. **Firm editing:** in item detail, partner, manager and senior edit why, what good looks like, blocks fieldwork, effort and the still-needed note; each change is audited; the send-back dialog says "The client will see this note".

**Non-goals**
- Comments and threads (A4, the next spec).
- AI-drafted why and what good looks like (B2, later; the firm approves, then it's plain text).
- Real-time co-editing.
- Gaps for anything but bank statements (other kinds use the still-needed note).
- Changing who can see which request (SPEC-020 rules stand).

## 5. User stories and acceptance criteria
**Story — Rachel knows what to send.** Rachel opens "Bank statements for December". It says why ("to confirm the cash balance at year end"), what good looks like ("the bank's own statement for each account, covering December 31, with opening and closing balances"), and "We have statements for accounts ending 2290 and 8812; we still need 4471". Her home says "3 left · 1 blocks fieldwork · about 1 hour".

- **AC-1** Given a client-visible request, then the client sees its description, why, what good looks like, due date, assignee and status; text is the firm's or fixed copy, never a model's.
- **AC-2** Given a request from a template with why and what good looks like, then they carry to the engagement; without them, fixed copy for the item's document kind applies; with neither, the fields are empty and not shown.
- **AC-3** Given partner, manager or senior, then they edit why, what good looks like, blocks fieldwork, effort and the still-needed note; others can't; each change is audited.
- **AC-4** Given an item fulfilled by a retrieval or an import, then the client sees it as provided, with the date and source, and no upload prompt.
- **AC-5** Given a bank statement item, a year-end trial balance and uploaded statements, then the client sees which cash accounts (last four digits) are covered and which are still needed, computed by code; with no trial balance or no cash accounts, no gap line is shown.
- **AC-6** Given a client user, then the client home shows, per engagement, their items left, how many block fieldwork, and the summed effort.
- **AC-7** Given a request with versions, then the client sees each version they may see, newest first, with who, when and its outcome; a send-back shows its reason label and the reviewer's note; a rejection's note isn't shown.
- **AC-8** Given a template workbook with the new columns, then they're imported and carried to engagements and roll-forwards; without them, the defaults apply.
- **AC-9** Given every new screen, then loading, empty, error and not-allowed states exist, and colours come only from tokens.

## 6. Design notes
- **Data:** `request_items` gains `why`, `good_looks_like`, `still_needed` (text, capped), `blocks_fieldwork` (boolean), `effort` (`small`, `medium`, `large`), each with a source (`template`, `kind_default`, `firm`); `methodology_request_items` gains the four template columns.
- **Fixed copy per kind** lives in code (requests), reviewed by the founder before release (Q1).
- **The gap** is computed in evidence (it already reads extractions and the year-end snapshot, SPEC-029) and exposed with the item's client view; no new storage.
- **Send-back reasons** come from `review_decisions` (evidence); the client view exposes the reason label and note for `send_back` decisions only.
- **API:** the client's request list gains the new fields and `provided` and `gap`; `GET /v1/me/your-part` (per engagement); `GET …/request-items/{id}/history` for clients; `PUT …/request-items/{id}/guidance` for the firm.

## 7. Delivery
- **TASK-060 (amber, backend):** fields, template columns and carry-over, kind defaults, firm editing, provided, the gap, history with send-back reasons, your part.
- **TASK-061 (amber, web):** the client request detail, your part on the client home, history; firm editing in item detail; the send-back dialog's notice.

## 8. Test plan
| AC | Level | What |
|---|---|---|
| AC-1, AC-2, AC-8 | unit, integration | Defaults from template and kind; carry-over on apply and roll-forward |
| AC-3 | unit, integration | Edits by role; audit |
| AC-4, AC-5 | unit | Provided wording; gap from synthetic trial balances and statements |
| AC-6 | unit, integration | Your part per role and assignment |
| AC-7 | integration | History visibility; send-back reasons shown, rejection notes hidden |
| AC-9 | vitest | New screens' states |

## 9. Open questions
All resolved: the founder approved every recommendation below on 2026-10-12.
- **Q1 — default copy.** *Recommendation:* fixed why and what good looks like per document kind in code (four kinds), which I'll draft for your review in TASK-060; templates override them; firms edit per engagement.
- **Q2 — partial requests beyond bank statements.** *Recommendation:* code computes the gap for bank statements only (it has the data); for anything else the firm writes a still-needed note the client sees.
- **Q3 — effort.** *Recommendation:* small, medium, large, counted as 15, 45 and 120 minutes for the estimate, shown rounded ("about 1½ hours"); defaults per document kind, firm-editable.
- **Q4 — send-back notes.** *Recommendation:* a send-back's note is always shown to the client (a send-back is a request to them), and the dialog says so; a rejection's note stays firm-only.
- **Q5 — blocks fieldwork.** *Recommendation:* a firm-set yes or no per item (default no, or from the template); the client home counts them and lists them first.
