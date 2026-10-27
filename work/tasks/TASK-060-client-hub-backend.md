---
id: TASK-060
title: "Client hub, part 1: guidance, provided, the bank statement gap, history and your part (backend)"
spec: SPEC-031
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8]
risk_zone: amber
status: done
branch: task-060-client-hub-backend
worktree:
created: 2026-10-12
updated: 2026-10-12
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-031 §7, TASK-060: the data and APIs behind the client hub. TASK-061 builds the screens.

## Scope
SPEC-031 AC-1 to AC-8.

## Context to load
- Spec: `docs/specs/SPEC-031-client-hub.md`; ADR-050, ADR-111
- Code: `engagements/workbook.py` (`HEADERS`, `TemplateItem`, `parse_workbook`), `engagements/repository.py` (template rows), `requests/service.py` (`insert_classified`, `_insert_item`, `RequestItemView`), `requests/roll_forward.py`, `requests/classification.py` (document kinds), `requests/routes.py`; `evidence/item_detail.py` (`item_versions`), `evidence/repository.py` (`item_versions_with_decisions`), `evidence/service.py` (`reason_codes`), `evidence/cross_checks.py` (`cash_accounts`), `evidence/processing.py` (`_accounts`)

## Plan
- [x] Plan approved by human (founder, 2026-10-12: D1–D5 as recommended; D3 copy as drafted). Approved by founder: the paths named in D5

### What the code shows
- **The workbook header is checked as a prefix** (`header[:len(expected)] == expected`), so extra columns after "area_code, description, tier" can be added without breaking existing templates.
- **Requests can't read evidence** (evidence depends on requests), so anything joining an item with its versions (provided, gap, history) belongs in evidence, as item detail already does.
- **Item history exists for the firm** (`item_versions`, firm side only, with decisions); clients have only their uploads list.
- **SPEC-029 already finds cash accounts** in the year-end trial balance (`cash_accounts`) and reads each statement's last four digits (`upload_extractions.account_last4`).

### Design (for founder review)
1. **Data** (migration 0047):
   - `request_items`: `why`, `good_looks_like`, `still_needed` (text, up to 1,000), `blocks_fieldwork` (default false), `effort` (`small`, `medium`, `large`, or null), `guidance_source` (`template`, `kind_default`, `firm`);
   - `methodology_request_items`: `why`, `good_looks_like`, `blocks_fieldwork`, `effort`.
2. **Templates** (engagements): optional workbook columns "why", "good_looks_like", "blocks_fieldwork" (yes or no), "effort" (small, medium, large) after the three required ones; validated, stored, carried when the methodology is applied and on roll-forward.
3. **Defaults by document kind** (requests, `guidance.py`), applied when an item is created without template guidance, and when its kind is set by rule while the guidance isn't the firm's own (D3 has the copy).
4. **Firm editing** (requests): `PUT …/request-items/{id}/guidance` (`request_item.update`: partner, manager, senior) for why, good looks like, still needed, blocks fieldwork and effort; source becomes `firm`; audited.
5. **The client's request list** gains why, good looks like, still needed, blocks fieldwork and effort (no new action: the list's existing visibility rules apply).
6. **Client view of one request** (evidence, D1): `GET …/request-items/{id}/client-view` (`evidence.read` with the item's client facts, as uploads):
   - `provided`: when the newest fulfilment is a retrieval or import, its source (`connection` or `export`) and date;
   - `gap` (bank statement items only): the cash accounts covered and still needed, each named by its last four digits, or by account name when it has none (D2), computed by code from the year-end snapshot and the item's statements; absent without a snapshot or cash accounts;
   - `history`: each version the person may see, newest first: who added it (the firm, or a name for client uploads), when, and its outcome (`in_review`, `accepted`, `sent_back` with the reason's label and the reviewer's note, `not_accepted` with no note) (SPEC-031 Q4).
7. **Your part** (requests): `GET /v1/engagements/{id}/your-part` for client roles: items left for the person (client-visible, open or needing revision, assigned to them, or unassigned for client admins), how many block fieldwork, and the estimated minutes (small 15, medium 45, large 120; an item without an estimate counts as medium, D4). The client home calls it per engagement.
8. **Tests:** workbook columns and carry-over; defaults; edit permissions and audit; provided; gap cases (all covered, one missing, no digits, no snapshot); history visibility (a contributor sees only their items; send-back reasons shown, rejection notes hidden); your part by role and assignment.

### Questions for the human
- **D1 — where client views live.** Recommended: provided, gap and history in evidence (it reads requests, extractions and the ledger); guidance and your part in requests. Alternative: a new module, which the module map doesn't have.
- **D2 — naming an account without digits.** Recommended: use its account name from the trial balance ("Payroll account"), the client's own data. Alternative: say only "1 account still needed".
- **D3 — the default copy** (SPEC-031 Q1), shown to clients verbatim; please confirm or edit:
  - **Bank statement** — Why: "To confirm the cash the company held at year end, we compare each bank account's balance with the bank's own record." What good looks like: "The bank's statement for every account, covering the year-end date and showing opening and closing balances. Download it from online banking as a PDF; a photo or scan is harder to read." Effort: small.
  - **AR aging** — Why: "To see who owes the company money at year end and for how long, and to check it agrees with your accounting system." What good looks like: "An aged receivables report as of the year-end date, by customer, with totals by age band, exported from your accounting system without edits." Effort: small.
  - **AP aging** — Why: "To see what the company owed its suppliers at year end and confirm nothing is missing." What good looks like: "An aged payables report as of the year-end date, by supplier, with totals by age band, exported from your accounting system without edits." Effort: small.
  - **Schedule** — Why: "To understand how a year-end balance is made up." What good looks like: "A spreadsheet listing each item that makes up the balance, with a total that agrees with your accounting system at year end." Effort: medium.
- **D4 — items without an effort.** Recommended: count them as medium in the estimate. Alternative: leave them out and say "plus N without an estimate".
- **D5 — approval file:** `backend/src/abacus/modules/evidence/**`, `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`, `backend/tests/unit/**`, `backend/tests/integration/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-12` — Design written for founder review after SPEC-031 merged (#108).
- `2026-10-12` — Built (D1–D5): migration 0047; template columns (validated, stored, carried on apply and roll-forward); `requests/guidance.py` with the D3 copy; `PUT …/guidance` (audited); `GET …/request-items/your-part`; evidence `GET …/client-view` (provided, bank statement gap, history). Unit tests (9,913) and gates pass. Local smoke on the Dev firm: kind default applied, firm edit audited, your part counted the blocking item, gap named the payroll account, history showed the client's upload in review.
- 2026-10-27: ADR-078 back-fill suite `backend/tests/integration/backfill/test_q03t047_requests_client_hub.py`; see `work/tasks/TASK-1438-*.md` (S11 lane 7).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Your part is `GET …/request-items/your-part`, not `/v1/me/your-part` | Stays on the requests router; a new router would need the protected `app.py` | No |
| History adds `replaced` for an undecided older version | "In review" would be wrong for a superseded upload | No |
| Accounts without digits take statements that match no account | A statement can't name an account the trial balance doesn't number (D2) | No |

## Handoff
Done. Next: TASK-061 (web): client request detail, your part on the client home, firm guidance editing, the send-back notice.
