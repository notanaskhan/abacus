---
id: TASK-046
title: The engagement setup page
spec: SPEC-025
acceptance_criteria: [AC-10, AC-9]
risk_zone: amber
status: done
branch: task-046-setup-page
worktree:
created: 2026-10-09
updated: 2026-10-09
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-025 task (d): one page per engagement that says where its setup stands. It has three parts:
- a narrative summary;
- a status checklist, showing each step's state and who acts next;
- a plain reason on every blocked item.

It's the engagement's default tab until the engagement opens.

## Scope
SPEC-025 AC-10, and AC-9 for this screen.

## Context to load
- Spec: `docs/specs/SPEC-025-act-1-the-engagement-opens.md` (the setup screen, AC-10)
- Code:
  - `engagements/setup.py` (`setup`, `SetupView`, `_blocked`), `engagements/routes.py` (`SetupOut`);
  - `engagements/service.py` (`engagement_team`, `contacts`, the methodology pin);
  - `apps/web`: `EngagementLayout`, `router.tsx` (the engagement index route), `People.tsx`, `EngagementRecords.tsx`, `Overview.tsx`.

## Plan
- [x] Plan approved by human (founder, 2026-10-09: D1–D4). Approved by founder: `backend/tests/unit/**`

### What the code shows
- **`GET …/setup` already returns the records:** acceptance, letter, everyone's confirmations, whether the letter is required, and the gate's reason code. It has no team, no request list state, no client contacts and no names of who acts next.
- **Engagements already owns every step's facts:**
  - client and period;
  - the team and its roles;
  - the methodology pin, which is the request list;
  - client contacts and their invitations;
  - acceptance, independence and the letter.

  The page needs no other module and no cross-module hook.
- **The records' panels live on the People tab today** (TASK-044). The engagement opens on Overview, which assumes the request list exists.

### Design (for founder review)
1. **The checklist is computed on the server (D1).** `GET …/setup` gains `steps` and `summary`. The checklist's order and wording are decided once, in code, and unit-tested. Each step has:
   - `key`;
   - `state`: `done`, `waiting`, `blocked`, `warning` or `not_needed`;
   - `detail` (for example "3 of 5 confirmed");
   - `next`: who acts next, as names and a role, for example "Dana Lee (engagement partner)";
   - `reason`: on `blocked` and `warning` only, a plain sentence.
2. **The eight steps, in the spec's order:**

   | Step | Done when | Otherwise |
   |---|---|---|
   | Client and period | always (set at creation) | n/a |
   | Team | there is an engagement partner | `waiting`, next: firm administrators |
   | Request list | a methodology is applied | `waiting`, next: partner or manager |
   | Acceptance | `accepted` | `waiting`, next: the partner; `blocked` if declined ("Declined by Dana on 3 Oct. Record it again if that changes.") |
   | Independence conclusion | the partner has concluded | `waiting`, next: the partner |
   | Each member's independence | everyone has `confirmed` | `waiting`, "3 of 5 confirmed", next: the people still to confirm; a decline shows as `warning` with "Sam declined" (the note only to the partner and manager, as today) |
   | Letter | `signed`, or `not_required_this_year` | `warning` when the firm doesn't require it ("Preferably signed before work starts"); `blocked` when it does |
   | Client contacts | at least one accepted contact | `blocked` while the engagement isn't open ("Client invitations open once Dana records acceptance."); otherwise `waiting`, next: partner or manager |

   The reasons reuse the gate's plain words (the same `errorMessage` mapping), so a refusal elsewhere and this page say the same thing.
3. **The narrative summary:** one or two plain sentences built from the steps, never by a model. For example:
   - "Northwind FY2026 audit (continuance): waiting for Dana Lee to record continuance. 3 of 5 have confirmed independence."
   - Once open: "Northwind FY2026 audit is open for client data. 4 of 5 have confirmed independence; Sam Patel hasn't yet."
4. **Web:**
   - a new **Setup** tab (`/engagements/$id/setup`), reading `GET …/setup`;
   - the page shows the summary, the checklist (each step with a state pill, detail, who's next, and the reason), and the existing acceptance, letter and independence panels from `EngagementRecords`, which move here from People;
   - People keeps the team and client contacts;
   - **default tab (D2):** while `blocked` is set, opening the engagement goes to Setup; once open, Overview stays the default;
   - each step links to where it's done: Team and Client contacts to People, Request list to Overview's "Apply a template", and the records to their panels on the same page;
   - loading, error and not-allowed (403 from `setup.read`) states, colours from tokens;
   - the client portal is unchanged: clients never see the setup.
5. **Tests:**
   - unit tests for the steps and the summary across states (new, accepted without conclusion, declined, letter required or not, partial independence, open);
   - vitest for the page (summary, checklist, reasons, the default-tab redirect, states);
   - a local smoke on a fresh engagement and on an open one.

**Protected paths:** none expected.
- No matrix change (`setup.read` already exists);
- no schema change and no migration;
- `api/app.py` isn't touched;
- identity isn't touched: names come from identity's existing `names_of`, through `identity.api`;
- `backend/tests/unit/**` is listed, as in earlier tasks.

### Questions for approval
- **D1. Compute the checklist and the summary on the server, inside `GET …/setup`, not in the browser?** *Recommendation: yes.* It's one tested place, and the text is the same wherever it shows later, for example in a notification or a digest.
- **D2. Open on Setup while the engagement isn't open, and on Overview after?** *Recommendation: yes,* as the spec says.
- **D3. Move the acceptance, letter and independence panels from People to Setup?** *Recommendation: yes.* People goes back to being about people, and the records sit beside their checklist steps.
- **D4. The request list step counts as done once a methodology is applied, without counting items?** *Recommendation: yes.* Engagements owns the pin; counting items would need a hook from the requests module for little gain.

## Definition of done
- [x] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [x] Type check, lint, format, architecture and dependency rules pass
- [x] Every query is tenant-scoped; every endpoint checks authorisation
- [x] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — Implemented:
  - `engagements/setup_steps.py`: the eight steps and the summary, computed from facts with no reads; `GET …/setup` returns `steps` and `summary` (`SetupStepOut`);
  - the setup view gathers the facts: the team, the methodology pin, the client's name, whether the client had earlier engagements, firm administrators' names (only when there's no partner), and client contact counts;
  - "has a partner" lives in `setup_steps.has_partner`, because AUTHZ-001 flags role comparisons in services; it names people and grants nothing;
  - web: a Setup tab (summary, checklist with state, detail, who's next, reason, and links to People or Overview), with the acceptance, independence and letter panels moved from People. The engagement opens on Setup while it isn't open, once per engagement per page load, so Overview stays reachable (for applying a template) after that.

  Tests and checks:
  - `test_setup_steps.py` (10 tests across states, including a reason on every blocked or warning step); web `spec025setup.test.tsx` (summary, checklist, reasons, the default-tab redirect, loading, error and not-allowed states);
  - backend unit 9,351 passed, web 193 passed, gates pass;
  - local smoke: a fresh engagement read "waiting for Dana Leader to record acceptance", with contacts blocked for that reason; after acceptance and the conclusion it read "is open for client data… Dana Leader hasn't yet".
- `2026-10-09` — Design written for founder review after TASK-045 merged (#81).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
