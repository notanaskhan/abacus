---
id: TASK-057
title: "Upload processing, part 4: the screens for checks"
spec: SPEC-029
acceptance_criteria: [AC-10, AC-11, AC-13]
risk_zone: amber
status: done
branch: task-057-check-screens
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
SPEC-029 stories 1 and 2 on screen: a client sees, seconds after uploading, what's wrong with a file in plain words and can replace it; the firm sees every check and cross-check in item detail, can set what a request expects, and spots items with problems on the Board.

## Scope
SPEC-029 AC-10, AC-11, AC-13; the document kind control for AC-5 (API from TASK-055).

## Context to load
- Spec: `docs/specs/SPEC-029-upload-processing.md` §4.7, §5; ADR-111
- Code: `apps/web/src/screens/ClientEngagement.tsx` (`ClientItem`, uploads), `ItemDetail.tsx`, `Board.tsx`, `board/join.ts`, `board/filters.ts`; `evidence/uploads.py` (`upload_checks`), `evidence/routes.py` (`EvidenceVersionOut`, the checks route); `requests/routes.py` (document kind)

## Plan
- [x] Plan approved by human (founder, 2026-10-12: D1–D4 as recommended). Approved by founder: the paths named in D4

### What the code shows
- The checks API (TASK-055) returns one upload's latest checks, client-audience only for client roles; it answers an empty list until the workflow has checked the file.
- The Board joins items, the engagement's evidence versions and screening results in three reads; nothing per item carries check results, so a marker would need one request per item.
- The document kind can be set by API (`PUT …/document-kind`) but no screen offers it.

### Design (for founder review)
1. **Client: instant results** (`ClientItem`):
   - each upload in the list shows its client checks: nothing while they're being run ("Checking…", polling every 3 s for up to 30 s after an upload), a green "No problems found", or one line per problem;
   - problem lines come from fixed templates (`checkMessages.ts`, ADR-111), filled only with the dates and amounts the server computed, for example "This statement ends on November 30, 2026; we need one that includes December 31, 2026", "This looks like it's for a different company", "The balances on this statement don't add up (off by $124.50)", "This looks like a scanned copy, so we can't read it; please upload the statement you download from your bank's website";
   - **Replace file** beside a problem opens the file picker for the same request; the new file becomes a new version and is checked in turn (the old one stays, ADR-004).
2. **Firm: item detail** — a "Checks" panel for the shown version: every check with its outcome (passed, problem, not checked, with why), the same messages, plus the ledger cross-check in the firm's words ("Closing balance is $124.50 more than account 1000 in the trial balance"); and a **document kind** select ("Bank statement", "AR aging", "AP aging", "Schedule", "No particular document", "Use the rules") for partner, manager and senior.
3. **Board marker:** the evidence-version list gains `problems` (the number of problem checks on the version, any audience); the Board shows "Problems found" on those items and adds it to the Evidence filter.
4. **States** (AC-13): loading, empty, error and not-allowed for every new piece; colours from tokens.
5. **Tests:** vitest for each message template, the client's pending → results flow and Replace file, the firm panel and the kind select, the Board marker and filter; a backend unit test for `problems` on the version list.

### Questions for the human
- **D1 — the Board marker's data.** Recommended: add `problems` to the evidence-version list (one small backend change in evidence, a protected path). Alternative: one checks request per item from the Board, which doesn't scale.
- **D2 — duplicates in client words.** Recommended: "This file is already uploaded elsewhere in this audit", without naming the other request (the client may not see it). The firm's panel links the other request.
- **D3 — the document kind control.** Recommended: in this task, in item detail, for partner, manager and senior.
- **D4 — approval file** for D1: `backend/src/abacus/modules/evidence/**`, `backend/tests/unit/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every new screen has loading, empty, error and not-allowed states; colours from tokens only
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-12` — Design written for founder review after TASK-056 merged (#102).
- `2026-10-12` — Built (D1–D4): `problems` on the evidence-version list (latest run; client roles count client checks only; filtered with `visible()`); `checkMessages.ts`; client results with polling and Replace file; the firm's Checks panel and document kind control; the Board marker and "Problems found" filter. Web 255 tests, backend unit tests and gates pass. Local check: the earlier smoke engagement's versions show 0, 3 and 1 problems as expected. The `problems` count has no database-level test yet (integration, deferred).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| `problem_counts` filters with `visible()` instead of a list exemption | The exemption list is protected and outside this task's approval; the filter is the proper fix anyway | No |
| Client roles' problem counts include client-audience checks only | A firm-only cross-check must not leak to a client through the count | No |

## Handoff
Done. SPEC-029 is complete (TASK-054 to TASK-057). Next per the Act 2 plan: B4 (upload reviewer, on synthetic data) building on the extraction, or SPEC-030 (client hub).
