---
id: TASK-043
title: Clients you already have, and invitations in the firm's name
spec: SPEC-025
acceptance_criteria: [AC-1, AC-8, AC-9]
risk_zone: amber
status: awaiting-plan-approval
branch: task-043-existing-clients
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
SPEC-025 task (a), first because it closes a walls gap:
- a new engagement picks a client the firm already has, instead of always creating one;
- client invitations go out in the firm's name.

## Scope
SPEC-025 AC-1, AC-8 and AC-9 (for these screens).

## Context to load
- Spec: `docs/specs/SPEC-025-act-1-the-engagement-opens.md`; ADR-026
- Code:
  - `organisations` (`create_client`, `names_in_firm`, `firm_names`);
  - `engagements.service.create_engagement` and `firm_router`;
  - identity `firms` and walls;
  - `communications/invitations.py` and `transport.py`;
  - `apps/web` `Engagements` (the create dialog), `ClientEngagement`.

## Plan
- [ ] Plan approved by human

### What the code shows
- **Every engagement creates a new client and entity:** `create_client` always inserts. A wall is on a client ID, so a second "Halvorsen" record isn't covered by a wall on the first.
- **Only firm administrators and practice leaders can create engagements** (`engagement.create`). The story's Maya is a manager (D3).
- **The invitation email doesn't name the firm, the client or the engagement,** and the transport has no sender name.

### Design (for founder review)
1. **Picking a client:**
   - `GET /v1/firm/clients/search?q=` (new matrix action `client.read`, held by `engagement.create`'s roles, D1) returns the firm's clients with their entities, matched on a normalised name (case, spacing and punctuation ignored, and common suffixes such as "Inc", "LLC", "Ltd" and "Corp" dropped, D2);
   - walled clients are left out for the person searching.
2. **Creating against an existing client:**
   - `POST /v1/engagements` accepts either `client_id` with `client_entity_id` (existing) or `client_id` with a new entity name, or names for a new client, as today;
   - for an existing client, the engagement is checked against the creator's walls before it's created (a walled creator is refused, as `authorise` does for everything else);
   - a new client whose normalised name matches an existing one is refused with 409 `possible_duplicate` (listing the matches) unless `confirm_new: true`.
3. **Data (organisations migration 0035):**
   - `clients.normalised_name` (generated from `name`), indexed;
   - `client_entities` unique per client on their normalised name, so the same entity can't be added twice.
4. **Invitations in the firm's name:**
   - **the email** now reads: subject "Whitfield & Lane invites you to their audit of Halvorsen"; body "Whitfield & Lane has invited you to share documents for their FY2026 audit of Halvorsen…";
   - **sender name:** the transport gains an optional sender display name, set to the firm's name. The sending address stays Abacus's until custom domains exist (SPEC-025 Q6);
   - **the portal:** the client engagement page shows "with Whitfield & Lane", and the client home already lists firms by name;
   - **names:** from new tenant-level reads in identity (`firm_name`) and engagements (`engagement_label`: engagement, client and period). Communications already depends on both.
5. **Web:** "New engagement" begins with a client picker:
   - search as you type, choose a client, then choose an entity or "Add an entity";
   - or "New client" (name and entity);
   - a likely duplicate shows "Did you mean …?" with the matches before creating.

   The rest of the dialog (name, period, type) is unchanged.

**Protected paths (approval file):**
- `backend/src/abacus/modules/identity/*` (top-level files only: the `firm_name` read);
- `docs/architecture/permission-matrix.yaml` and the generated `backend/src/abacus/modules/identity/authz/_matrix.py` (`client.read`, D1);
- `backend/src/abacus_tools/quality/schema_check.py` (the new column and index);
- `backend/src/abacus_tools/quality/banned_patterns.py` (if the search needs LIST-001 handling);
- `backend/tests/unit/**`.

Not needed:
- `api/app.py`: the routes go on the existing `firm_router`;
- `identity/authz` beyond the generated matrix file;
- organisations, engagements, communications and `apps/web`: not protected.

### Questions for approval
- **D1. Add `client.read` for the client picker, held by the same roles as `engagement.create`?** *Recommendation: yes.*
- **D2. Detect duplicates by normalised name (case, spacing, punctuation and common legal suffixes ignored), refusing a likely duplicate unless confirmed?** *Recommendation: yes.*
- **D3. The story's Maya is a manager, but only firm administrators and practice leaders can create engagements today. Keep it that way for now and note the story mismatch, or let managers create engagements?** *Recommendation: keep it for now.* Letting engagement-level roles act at firm level is an authorisation change (inside `identity/authz`, which stays excluded). If you want managers to create engagements, the clean way is a firm-level role or setting ("can open engagements"), as its own small spec.
- **D4. Write the approval file for the paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — SPEC-025 approved and merged (#78). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
