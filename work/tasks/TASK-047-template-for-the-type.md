---
id: TASK-047
title: New engagement offers the firm's template for its type
spec: SPEC-025
acceptance_criteria: [AC-3, AC-9]
risk_zone: amber
status: done
branch: task-047-type-template
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
SPEC-025 task (b), narrowed by the founder: creating an engagement offers the firm's template for the engagement's type, at its latest version, so the request list exists from the start. Rolling forward from last year's engagement (AC-2) is a later task.

## Scope
SPEC-025 AC-3 (the proposal for a new client is the firm's template for the type, and no team beyond the creator), and AC-9 for the changed screens.

## Context to load
- Spec: `docs/specs/SPEC-025-act-1-the-engagement-opens.md` (AC-3)
- Code:
  - `engagements` (`list_templates`, `TemplateVersionOut`, `create_engagement`, `pin_methodology`, `TemplateTypeMismatch`);
  - `requests.service.apply_methodology` (`engagement.apply_methodology`);
  - `apps/web`: `Engagements.tsx` (the create dialog), `Overview.tsx` (`ApplyMethodology`).

## Plan
- [x] Plan approved by human (founder, 2026-10-09: D1–D3). Approved by founder: `backend/tests/unit/**`

### What the code shows
- **Creating an engagement never offers a template.** The request list is applied afterwards, from Overview's "Start from your methodology" (`engagement.apply_methodology`, held by the engagement partner and manager).
- **That picker lists every version of every template for the type,** old versions included. AC-2 and AC-3 call for the latest version.
- **No template is marked as the firm's default for a type.** A type is served by zero, one or several templates (SPEC-024).
- **The creator becomes the engagement partner in the creating unit of work,** so they may apply the methodology straight after.
- **AC-3's "no team beyond the creator" already holds.**
- **Seeding request items belongs to `requests`,** which depends on engagements, not the other way round.

### Design (for founder review)
1. **The create dialog gains a "Request list" choice**, shown once the type is chosen:
   - **one template serves the type:** it's preselected ("Northwind audit methodology · v4 (latest)"), with "Start with an empty list" as the alternative;
   - **several templates serve it:** the creator picks one, each shown at its latest version, or starts empty; nothing is preselected (D2);
   - **none serves it:** "Your firm has no template for audits yet", with a link to Methodology for those who manage it. The engagement is created with an empty list.
2. **Two calls, in order (D1):**
   - `POST /v1/engagements` creates the engagement, with the creator as engagement partner, as today;
   - then `POST /v1/engagements/{id}/methodology` applies the chosen version, as Overview does;
   - if applying fails, the engagement still exists, the dialog says "Created, but the template wasn't applied: {reason}", and the setup page's Request list step offers it again.

   No new endpoint, no matrix change, and no new link between the engagements and requests modules.
3. **Latest versions only (D3):**
   - `GET /v1/methodology/templates` gains `?latest=true`, returning each template's newest version only (filtered in the repository query);
   - the dialog and Overview's picker both use it;
   - the Methodology screen keeps the full history.
4. **Web:**
   - the dialog's new section, with loading, empty ("no template for this type") and error states;
   - after creating, the engagement opens on Setup (TASK-046), where the Request list step shows done or waiting.
5. **Tests:**
   - unit tests for the latest-only listing;
   - vitest for the dialog: one template preselected, several to choose from, none, empty chosen, and the apply failing after creation;
   - a local smoke creating an engagement with the Dev firm's template.

**Protected paths:** none expected.
- No matrix change (`methodology.read` covers the listing for firm administrators and practice leaders, who create engagements);
- no schema change;
- `api/app.py`, identity, evidence and connections aren't touched;
- `backend/tests/unit/**` is listed, as in earlier tasks.

### Questions for approval
- **D1. Apply the template with a second call from the browser, straight after creating, rather than inside the create request?** *Recommendation: yes.*
  - Doing it in one request would need a new hook from `requests` into engagements.
  - It would also mean authorising `engagement.apply_methodology` for a partner role written earlier in the same transaction.
  - A failed apply leaves an engagement with an empty list. That's visible and fixable on the setup page.
- **D2. With several templates for a type, preselect none and ask, rather than adding a "firm default per type" setting?** *Recommendation: yes for now.* A default needs a schema change and a settings screen. Most firms have one template per type, and that case is preselected.
- **D3. Offer only each template's latest version, in the dialog and on Overview?** *Recommendation: yes,* matching AC-2 and AC-3. Older versions stay visible on the Methodology screen.

## Definition of done
- [x] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [x] Type check, lint, format, architecture and dependency rules pass
- [x] Every query is tenant-scoped; every endpoint checks authorisation
- [x] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — The template-version bug found below is fixed on its own branch (founder: "fix the template bug first"). Version numbering now takes a transaction-scoped advisory lock keyed on the template (`pg_advisory_xact_lock`), not `FOR UPDATE`, so no grant or migration is needed and the table stays insert-only. Local check: version 2 imported, then three concurrent imports numbered 3, 4 and 5. A unit test pins the lock.
- `2026-10-09` — Implemented:
  - `GET /v1/methodology/templates?latest=true` (repository: versions with no newer version of the same template);
  - "New engagement" gains the Request list choice: the only template for the type preselected at its latest version, several to choose from, none explained with a link to Methodology, or "Start with an empty list". It creates, then applies (D1), then opens the engagement (on Setup while it isn't open). A failed apply says "Created, but the template wasn't applied", with the reason and a link to the engagement;
  - Overview's picker offers latest versions only.

  Tests and checks:
  - backend `test_latest_templates.py`; web `spec025template.test.tsx` (preselected and applied, several, empty list, none, failed apply);
  - the existing create test now expects the new engagement to open (the approved behaviour), keeping its request-body and list-refresh checks;
  - backend unit 9,353 passed, web 198 passed, gates pass;
  - local smoke: the Dev firm's imported template was listed at its latest version, applied by the creator straight after creating (8 items), and the setup page's Request list step showed done.
  - **Found, not fixed (out of scope):** importing a *second* version of an existing template fails locally with "permission denied for table methodology_templates". The import locks the template row (`SELECT … FOR UPDATE`), which needs UPDATE privilege that the app role doesn't hold on that table. It needs a small fix of its own (a migration grant or a different lock), reported to the founder.
- `2026-10-09` — Design written for founder review after TASK-046 merged (#82).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
