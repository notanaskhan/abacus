---
id: TASK-064
title: "Content matching, part 1: code suggestions from what's in an inbox file, with reasons"
spec: SPEC-033
acceptance_criteria: [AC-1, AC-2, AC-6, AC-9]
risk_zone: amber
status: done
branch: task-064-content-rules
worktree:
created: 2026-10-13
updated: 2026-10-13
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-033 §7, TASK-064: code-only content suggestions for inbox files, for every firm. The matcher agent follows in TASK-065 and TASK-066.

## Scope
SPEC-033 AC-1, AC-2, AC-6, AC-9 (for the code suggestions).

## Context to load
- Spec: `docs/specs/SPEC-033-content-matching.md`; SPEC-023; SPEC-029; SPEC-031 (the gap)
- Code:
  - `evidence/matching.py` (`suggest`, `Suggestion`);
  - `evidence/inbox.py` (`_entries`, `assign`);
  - `evidence/routes.py` (`SuggestionOut`, `InboxFileOut`, the assign body);
  - `evidence/client_view.py` (`statement_gap`, `year_end_accounts`);
  - `evidence/repository.py` (`extraction_for`);
  - `evidence/checks.py` (entity comparison);
  - `apps/web/src/screens/InboxPanel.tsx`

## Plan
- [x] Plan approved by human (founder, 2026-10-13: D1–D3 as recommended). Approved by founder: the paths named in D3

### What the code shows
- **Inbox suggestions** come from `suggest(file_name, items)`: word overlap plus a classification-rule bonus, at most three, a minimum score of 35, with the matched words.
- **Each inbox file is extracted** (`upload_extractions` by `inbox_file_id`). The record holds the statement fields (period start and end, opening and closing, account last four, account holder) or the aging fields (as-of date, grand total), but **no detected document kind**. A statement shows as statement fields; an aging as an as-of date and total. AR and AP agings can't be told apart from these columns (D2).
- **The bank statement gap** (SPEC-031) is computed in `client_view` from the year-end trial balance and the item's uploads.
- **Assignment** records only `followed_suggestion` (a boolean).

### Design (for founder review)
1. **Facts from the extraction** (`matching.py`, pure). These are read from the extraction's columns only, so listing the inbox never loads stored documents:
   - **kind:** `bank_statement` when the statement fields are present (a period end, plus a closing balance or account digits); `aging` when an as-of date and a grand total are present;
   - **date:** the period end or as-of date;
   - **account digits** and **account holder**.
   - An unreadable or not-yet-extracted file has no facts, and falls back to the file name alone.
2. **Scoring each assignable request** (pure; at most 100; shown at 35 or more; top three):
   - **kind:** +50 when the request's document kind matches. A statement matches `bank_statement`; an aging matches `ar_aging` and `ap_aging` alike (D2);
   - **date:** +20 when the statement's period covers the engagement's year end, or the aging is as of it;
   - **account:** +30 when the digits are among the accounts the request still needs (SPEC-031 gap), or appear in its description;
   - **holder:** +10 when the account holder matches the client entity, using the same normalised comparison as the wrong-entity check;
   - **file name:** the SPEC-023 score × 0.4, so a good name still helps but no longer decides alone. A file with no facts keeps today's file-name score unchanged.
3. **Reasons:** each suggestion carries fixed codes with values. The screens render the labels:
   - `kind`: "Bank statement" or "Aging report";
   - `date`: "Covers December 31, 2026" or "As of December 31, 2026";
   - `account`: "Account ending 4471";
   - `holder`: "In the company's name";
   - `file_name`: "File name: bank, december".

   `source` is `content` when any content reason applies, otherwise `file_name`. `score` and `matched` stay as they are, for compatibility.
4. **The gap per bank statement request** is computed once per inbox listing: the year-end accounts, plus the digits already covered on each bank statement request. The code is refactored out of `client_view` into a shared helper, so the client view and the inbox agree.
5. **Assignment audit (AC-6):**
   - the assign body gains `suggestion_source` (`file_name`, `content`, or omitted) and `suggestion_rank` (1–3);
   - the audit event records both as integers, alongside `followed_suggestion`;
   - TASK-066 adds `matcher`.
6. **Screens** (the Inbox panel, firm and client): each suggestion shows the request's description and its reasons as small labels; a content suggestion is marked "From the file's contents". Assigning a suggestion sends its source and rank. Loading, empty, error and not-allowed states stay as they are.
7. **Tests:**
   - unit: facts from extraction rows; scores and reasons; digits and the gap decide between two bank statement requests (AC-2); a file without facts keeps the file-name result; a misleading name loses to the content;
   - integration: the inbox route returns reasons and source, and the audit records source and rank;
   - vitest: reasons, the content label, and the source and rank sent on assign;
   - a local smoke: drop synthetic statements named "scan0042.pdf" into a Dev engagement's inbox and check the suggestions.

### Questions for the human
- **D1: weights.** Recommended: the weights above (kind 50, date 20, account 30, holder 10, file name × 0.4). They're tuned by the evaluation suite in TASK-065, which runs the same cases on the code rules alone.
- **D2: AR or AP.** The extraction can't tell receivables from payables agings. Recommended: treat them alike in code (both get the kind points), and let the file name and request words break the tie; the matcher (TASK-065) reads the text. Alternative: add an extractor v2 that records the aging's side from its headings ("customer", "vendor"). That would need a new extractor version and a re-extraction of existing files.
- **D3: approval file:**
  - `backend/src/abacus/modules/evidence/**`;
  - `backend/tests/unit/**`, `backend/tests/integration/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-13` — Design written for founder review after SPEC-033 merged (#114).
- `2026-10-13` — Built (D1–D3): content facts and scoring with reasons; shared gap helpers; suggestion source and rank in the assignment audit; the Inbox panel's reasons and "From the file's contents". Unit (10,112) and web (305) tests and gates pass. Local smoke on a Dev engagement: "scan0042.pdf" (a statement) was suggested to bank statement requests on kind, year end and holder; an aging named "bank.xlsx" went to the AR aging request.
- `2026-10-26` — Back-filled by Q-03-T033: `backend/tests/integration/backfill/test_q03t033_matcher.py` (AC-1, AC-2, AC-6); see TASK-1284.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Equal scores tie between several bank statement requests when no account digits help | Code has nothing more to go on; the matcher (TASK-065) reads the text | No |

## Handoff
Done. Next: TASK-065 (the matcher agent and its evaluation suite).
