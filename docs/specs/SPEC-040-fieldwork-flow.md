---
id: SPEC-040
title: "Fieldwork, part 3: the flow — a manager approves the sample, one support request per sample, preparer and reviewer sign-off on each row, and the steps shown"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-050, ADR-111, ADR-131, ADR-132]
related_specs: [SPEC-037, SPEC-038]
created: 2026-10-20
updated: 2026-10-20
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Journal entry testing (SPEC-037) and the search for unrecorded liabilities (SPEC-038) select items and record results, but three controls an audit firm expects are missing. This spec adds them to both procedures:
- **sample approval:** a manager or the engagement partner approves the selection before anyone asks the client for support or records a result;
- **one support request per sample:** the selected items go to the client in a single request listing them all, instead of one request per entry;
- **row sign-off:** a preparer signs each tested row, and a reviewer who isn't the preparer signs it again. A sign-off goes stale when the row's result changes. The workpaper can be signed only when every row is signed at that level.

The screen shows the procedure's steps:
1. population tied;
2. selected;
3. approved;
4. support requested;
5. tested;
6. rows prepared;
7. rows reviewed;
8. workpaper signed.

It also sorts results into **Exceptions · Needs input · Passed**. The planning corpus (S09 AUD-11 and AUD-12, epic P-04) designs the same controls, and so does the competitor's flagship flow.

## 2. Problem and context
- Anyone on the team can record results on a selection nobody approved. Firms require a reviewer to agree the sample, both its size and its basis, first.
- `request_support` makes one client request per entry, so 40 selected payments mean 40 requests in the client's list.
- Sign-off is only at the workpaper level (ADR-131: `draft → ready → reviewed`). Nothing shows who prepared or reviewed each tested row, and nothing marks a row changed after sign-off.
- The Fieldwork tab shows cards, not where the procedure is in its life.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Staff / senior (preparer) | Records results; signs rows as preparer |
| Manager / engagement partner | Approves the sample; signs rows as reviewer (manager, senior or partner) |
| EQR (`reviewer` engagement role) | Never signs rows or approves samples (signs only at L5, epic P-04 R-SO-3) |
| Agent | Never approves, signs or sends (`agent: deny`) |
| Client | Sees one request for the sample |

## 4. Goals and non-goals
**Goals**
- Approval of the current selection by a named manager or partner, recorded and audited, and voided by selecting again.
- No results, support requests or row sign-offs on an unapproved selection.
- One client request per approved selection, listing its items. The link from each item to that request is kept, so each item's support is still traceable.
- Row sign-offs at two levels (prepared, reviewed). Each is bound to the result it signed, goes stale on a newer result, and can't be signed twice at a level by the same person.
- The workpaper's preparer sign-off requires every row prepared and current; its reviewer sign-off requires every row reviewed and current.
- A step tracker and triage counts on each procedure.

**Non-goals**
- Levels L3–L5, review notes and the full P-04 sign-off engine (epic P-04).
- Sample size calculators, sample expansion with an approver, and overriding size below methodology (epic A-03/A-08).
- Agent-drafted request wording (ADR-111). The request is fixed wording from code.
- Changing how items are selected.

## 5. User stories and acceptance criteria
### Story 1: approve the sample
- **AC-1** Given a procedure with a selection, when a manager or the engagement partner approves it, then the approval records who approved it, when, and the selection it covers. The procedure shows **Approved by {name}**, and an audit event is written. Staff, seniors, the EQR and the agent are refused (403).
- **AC-2** Given an approved selection, when anyone selects again, then the new selection is unapproved. The old approval stays in the history, and the procedure needs a new approval.
- **AC-3** Given an unapproved selection, when anyone records a result, requests support or signs a row, then it's refused with `sample_not_approved` (409).

### Story 2: one support request
- **AC-4** Given an approved selection, when a preparer requests support, then one client request is made for the selection:
  - its wording, from code, lists each item's date, reference and amount, as many as fit in a request's 2,000 characters, then "and n more"; the full list stays on the procedure and its workpaper;
  - each item still without support is linked to that request;
  - asking again, before new items need it, makes nothing new (409 `already_requested`).
- **AC-5** The per-entry "Request support" remains for one entry, and only on an approved selection.

### Story 3: sign each row
- **AC-6** Given a row with a result, when a staff member, senior or manager signs it as preparer, then the sign-off records the result it signed, who signed it and when. The partner and the EQR can't sign as preparer.
- **AC-7** Given a prepared row, when a senior, manager or partner who didn't prepare it signs it as reviewer, then the sign-off is recorded. The preparer of that row, the EQR and the agent are refused.
- **AC-8** Given a signed row, when a newer result is recorded, then its sign-offs show **Changed after sign-off** and no longer count. Sign-offs are never deleted.
- **AC-9** A preparer can sign several rows at once (bulk), each bound to its own current result. Rows already signed by them are skipped.
- **AC-10** The workpaper's "Sign off as preparer" is refused with `rows_not_prepared` until every row is prepared on its current result. "Sign off as reviewer" is refused with `rows_not_reviewed` until every row is reviewed.

### Story 4: see where the procedure is
- **AC-11** Each procedure shows the eight steps (§1) as done, current or to do, worked out from its state by code.
- **AC-12** The selected-items list shows counts of **Exceptions** (result `exception`), **Needs input** (no result, or `not_tested`) and **Passed** (`supported`). Each row shows **P** and **R** slots with the signer's initials, or empty.

## 6. Behaviour and flows
**Happy path:** select (existing) → a manager approves → a preparer requests support (one request) → the client uploads → the preparer records results → the preparer signs rows (bulk) → a reviewer signs rows → the preparer signs the workpaper → the reviewer signs the workpaper.

**State (derived, not stored):**

| Step | Done when |
|---|---|
| Population tied | the selection's population is tied |
| Selected | a current selection exists |
| Approved | the current selection has an approval |
| Support requested | every item that needs support is linked to a request |
| Tested | every row has a result |
| Rows prepared | every row has a current preparer sign-off |
| Rows reviewed | every row has a current reviewer sign-off |
| Workpaper signed | the workpaper is `reviewed` on its newest version |

## 7. Data
- `selection_approvals` (insert-only): `tenant_id`, `selection_id`, `approved_by`, `note`, `created_at`. One per selection (unique). RLS forced.
- `item_signoffs` (insert-only): `tenant_id`, `selected_item_id`, `item_result_id`, `level` (`prepared` | `reviewed`), `signed_by`, `created_at`. Unique on (`item_result_id`, `level`, `signed_by`). RLS forced.
- A sign-off is current when its `item_result_id` is the item's newest result.

## 8. Permissions (matrix)
- `sample.approve`: engagement_partner, manager; `agent: deny`; independence required.
- `item.sign_prepared`: staff, senior, manager; `agent: deny`; independence required.
- `item.sign_reviewed`: senior, manager, engagement_partner; `agent: deny`; independence required. The service also refuses the row's preparer.

## 9. Open questions (with recommendations)
- **Q1: who approves the sample?** *Recommendation:* manager or engagement partner, matching the corpus ("A manager must approve the sample first"). Seniors can't.
- **Q2: does approval block recording results, or only client requests?** *Recommendation:* both, so nothing is tested on a sample nobody agreed. Results already recorded on today's unapproved selections stay, and the gate applies from now.
- **Q3: workpaper gating.** *Recommendation:* gate the workpaper's sign-offs on row sign-offs (AC-10). That makes row sign-off mandatory, which is the point.
- **Q4: one request's wording.** *Recommendation:* fixed code wording, listing items. A request holds 2,000 characters (about 55 items); the rest are counted as "and n more".
- **Q5: the partner as preparer.** *Recommendation:* no, per ADR-131 Q2 (TASK-089 already removed it at workpaper level).
