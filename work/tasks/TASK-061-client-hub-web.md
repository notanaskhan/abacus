---
id: TASK-061
title: "Client hub, part 2: the client's request detail, your part, history, and the firm's guidance editing (web)"
spec: SPEC-031
acceptance_criteria: [AC-1, AC-3, AC-4, AC-5, AC-6, AC-7, AC-9]
risk_zone: amber
status: done
branch: task-061-client-hub-web
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
SPEC-031 §7, TASK-061: the screens on top of TASK-060's APIs.

## Scope
SPEC-031 AC-1, AC-3 (screen), AC-4 to AC-7 (screens), AC-9.

## Context to load
- Spec: `docs/specs/SPEC-031-client-hub.md`; TASK-060 (merged, #109)
- Code: `apps/web/src/screens/ClientEngagement.tsx` (`ClientItem`), `ClientHome.tsx` (`ClientEngagements`), `ItemDetail.tsx` (header, `DocumentKindSelect`, `DECIDERS`), `DecisionActions.tsx` (send-back note), `checkMessages.ts` (fixed-copy pattern)

## Plan
- [x] Plan approved by human (founder, 2026-10-12: D1–D3 as recommended)

### What the code shows
- **The client's request row** (`ClientItem`) shows the description, status, the upload input and a "Show uploads" list with checks and preview. The only "provided" line is for the trial balance import.
- **The client home** lists engagements with their periods, nothing about the work.
- **Item detail** already has a firm-only control row (document kind) and a role set for partner, manager and senior (`DECIDERS`).
- **The send-back dialog** has a note field with no word on who reads it.

### Design (for founder review)
1. **The client's request** (`ClientItem`; AC-1, AC-4, AC-5):
   - under the description: **Why we ask** and **What good looks like** when present, then the firm's **still needed** note; due date and assignee as now;
   - **provided** (from `client-view`): "Provided from your accounting system on {date}" or "Provided from your export of {date}", with no upload input. This replaces the trial-balance-only line;
   - **gap** (bank statement items): "We have statements for accounts ending 2290 and 8812; we still need 4471". An account without digits is named ("the Payroll account"). With nothing covered: "We still need statements for accounts ending …"; with nothing missing, no line;
   - a **Blocks fieldwork** badge; those items are listed first (SPEC-031 Q5).
   - All wording lives in a new `clientHubMessages.ts`, as fixed templates (ADR-111).
2. **History** (AC-7, D1): "Show uploads" becomes **"Show history"**. It lists `client-view` history newest first, joined by version to the uploads list, so file name, preview and checks stay:
   - who: "Added by your auditor", or the client's name;
   - when;
   - the outcome: "In review", "Replaced", "Accepted", "Not accepted", or "**Sent back: {reason}**" with the reviewer's note quoted.
   - Retrieved and imported versions show as "Provided from your accounting system" or "Provided from your export".
3. **Your part on the client home** (AC-6), on each engagement row: "6 left · 2 block fieldwork · about 1½ hours"; "Nothing left for you" at zero; a skeleton while loading; nothing on error (the engagement link still works). For the estimate wording, see D2.
4. **Firm guidance editing** (AC-3). Item detail gains a **Client guidance** section under the controls:
   - the current why, what good looks like, still needed, blocks fieldwork and effort;
   - a source label: "Default for bank statements", "From the template" or "Written by your team";
   - **Edit**, for partner, manager and senior only, opens a form: three text areas with a 1,000-character counter, a "Blocks fieldwork" checkbox and an effort select (Small, about 15 minutes; Medium, about 45; Large, about 2 hours). **Save** calls `PUT …/guidance`. Other roles see the section read-only.
5. **The send-back dialog** (SPEC-031 goal 7, Q4): under the note, "The client will see this note" for a send-back, and "Only your team sees this note" for a rejection.
6. **States** (AC-9): every new piece has loading, empty, error and not-allowed states, with colours from tokens only.
7. **Tests** (vitest): guidance shown and hidden; provided replaces the upload input; gap wording (all covered, some missing, no digits, none); history outcomes, with the send-back reason and note shown and a rejection showing no note; your part wording and rounding; the editing form by role; the dialog notice. A local smoke on the dev stack as Casey Client and the practice leader.

### Questions for the human
- **D1 — history placement.** Recommended: merge it into the existing uploads list ("Show history"), so each file shows its outcome beside its checks and preview. Alternative: a separate History section under the uploads.
- **D2 — estimate wording.** Recommended: under an hour, "about N minutes" (rounded to 15); otherwise to the nearest half hour ("about 1½ hours", "about 3 hours"). Alternative: always in hours.
- **D3 — approval file:** none expected. `apps/web/**` and `packages/api-client/**` aren't protected paths, and the API client was regenerated in TASK-060.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format pass
- [ ] Screens use the generated client only; colours from tokens only
- [ ] The relevant docs are updated

## Progress log
- `2026-10-12` — Design written for founder review after TASK-060 merged (#109).
- `2026-10-12` — Built (D1–D3): the client's request (guidance, due date, provided, gap, blocks-fieldwork badge and order), history merged into the uploads list with outcomes and send-back notes, your part on the client home, the firm's Client guidance panel with editing for partner, manager and senior, and the send-back dialog's notice. Wording in `clientHubMessages.ts`. Vitest (280) and gates pass; the live API serves the new routes.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The trial-balance-only "provided" line is replaced by `client-view` | It covers every retrieved or imported item | No |
| A gap mixing numbered and unnumbered accounts names each ("account ending 4471 and the Payroll account") | Caught by the wording test | No |

## Handoff
Done. SPEC-031 is complete. Next per the Act 2 plan: A4 comments spec.
