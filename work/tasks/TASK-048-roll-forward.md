---
id: TASK-048
title: Roll forward from last year's engagement
spec: SPEC-025
acceptance_criteria: [AC-2, AC-9]
risk_zone: red
status: planned
branch: task-048-roll-forward
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
SPEC-025 AC-2: when the client entity had an engagement of the same type for an earlier period, "New engagement" proposes three things, and nothing is created until a person confirms:
- last year's team;
- the template last year used, at its latest version;
- the request list rolled forward from what was actually used.

What they confirm is exactly what's created, in one step.

## Scope
SPEC-025 AC-2, and AC-9 for the wizard. AC-3 (new clients) shipped in TASK-047.

## Context to load
- Spec: `docs/specs/SPEC-025-act-1-the-engagement-opens.md` (roll-forward proposals, AC-2, the edge cases, `POST /v1/engagements/proposal`)
- Code:
  - `engagements.service.create_engagement`, `pin_methodology`, `_detail`, `list_templates`;
  - `requests.service.apply_methodology`, `_insert_item`, `RequestItem`;
  - identity `team.add_member`, `repository.team_candidate_ids`, `service.add_creator_as_partner`;
  - `apps/web` `Engagements.tsx` (the create dialog).

## Plan
- [ ] Plan approved by human

### What the code shows
- **"Actually used" is already recorded:** accepting evidence sets the request item's status to `accepted`, so the requests module can tell used items apart without reading evidence. Waived and not-applicable items aren't `accepted`, so they come over unticked, as the founder specified.
- **Engagements can't read request items,** because requests depends on engagements. The proposal and the copying of items need a hook from requests (ADR-106), as walls and independence already use.
- **Last year's team can't be copied with today's `add_member`:**
  - it checks the caller's own role through a separate database session;
  - inside the creating transaction, that session can't yet see the creator's new partner row, so the check fails.
  - The copy needs its own identity function, authorised by the creation itself, as `add_creator_as_partner` is.
- **Who creates engagements:** only firm administrators and practice leaders, and neither can read another engagement's request items today. The proposal needs its own read permission.
- **Engagements don't link to their prior engagement.**

### Design (for founder review)
1. **Finding last year's engagement:**
   - same client entity and type, the latest whose period ends before the new one starts;
   - if several match, the latest is proposed and the others are offered as a choice (spec edge case);
   - archived engagements count;
   - an engagement of a different type is ignored, and the new client path (TASK-047) is offered instead.
2. **The proposal: `POST /v1/engagements/proposal`.** Nothing is stored. It takes the client entity, type and period, plus an optional chosen prior engagement, and returns:
   - **prior:** which engagement, plus the other candidates;
   - **team:** last year's staff team with roles, each `available`, or `not_available` ("left the firm or now walled from this client") and so not offered. The creator isn't listed, because they become an engagement partner as today (D4);
   - **template:** the template last year used, its version then, and its latest version now;
   - **items** (up to 2,000):
     - `used` (accepted last year): ticked;
     - `not_used` (everything else, including waived and not applicable): unticked;
     - `new_in_template` (in the latest template version, with no matching item last year by area and description, ignoring case and spacing): flagged, ticked (D5);
     - each item carries its description, area, tier and client visibility.
3. **Creating from the proposal: `POST /v1/engagements` gains optional `roll_forward`.** It holds the prior engagement id, the confirmed team (person and role), the template version, the ticked prior item ids, and the ticked template additions. One unit of work does all of it:
   - creates the engagement with `prior_engagement_id`;
   - makes the creator a partner;
   - adds the confirmed team through identity's new `add_rolled_forward_member`. Each person is re-checked as active, staff and not walled; anyone unavailable is refused (409, nothing is created);
   - pins the latest version;
   - asks requests (through the hook) to create the ticked items with status `open`, keeping description, area, tier, dataset and client visibility, but no client assignee;
   - records the audit event `engagement.rolled_forward` (prior engagement, counts kept and dropped).

   Each new member gets their independence request (TASK-044), and the engagement opens on Setup.
4. **Permissions:**
   - the new matrix action `roll_forward.read` is held by `engagement.create`'s roles;
   - it's checked by `authorise` **on the prior engagement**, so walls apply. A creator walled from the client can't see the proposal (or create against that client, TASK-043);
   - it's a read action, so an archived prior engagement still works;
   - creating still requires `engagement.create`.
5. **Hooks (D1):**
   - requests registers two functions with engagements: `proposed_items(tenant, prior_engagement_id, latest_version)` and `copy_items(tx, ...)`;
   - unregistered means no roll-forward: the proposal says so, and creating with `roll_forward` is refused.
6. **Data:** engagements migration 0037 adds `engagements.prior_engagement_id` (nullable, the same tenant, set only at creation), plus the schema-check entry.
7. **Web: "New engagement" becomes a short wizard (spec §13):**
   - **Step 1:** client, entity, name, type and period, as today.
   - **Next:** asks for the proposal.
     - **With a prior engagement — step 2, review:**
       - the team (tick or untick, change role);
       - the template line ("Audit core v4, v3 last year");
       - items grouped as Used (ticked), Not used (unticked) and New in the template (flagged), with counts ("62 of 75 used, 13 not used, 3 new");
       - then **Create** in step 3.
     - **Without one:** the TASK-047 template choice, unchanged.
   - Loading, error and not-allowed states; colours from tokens.
8. **Tests:**
   - unit tests for the proposal rules: used vs not used, waived and not applicable unticked, new in the template, matching, prior selection with several candidates, a different type ignored, unavailable people;
   - the identity function: walled, inactive or client people refused;
   - the create path, with the hook refusing an unknown prior item;
   - vitest for the wizard;
   - a local smoke rolling forward a seeded engagement with accepted items.

**Protected paths (approval file), each named:**
- `docs/architecture/permission-matrix.yaml` and the generated `backend/src/abacus/modules/identity/authz/_matrix.py`: `roll_forward.read` (D3);
- **`backend/src/abacus/modules/identity/service.py` and `identity/api.py`: `add_rolled_forward_member` (D2).**
  - *Why identity:* team membership is identity's table, and `add_member` can't run inside the creating transaction (see above).
  - The new function reuses `team_candidate_ids` (active staff, not walled, not already on the team), the audit event and the member-added hook.
  - It doesn't touch `identity/authz`.
- `backend/src/abacus_tools/quality/schema_check.py`: `prior_engagement_id` as an app insert column;
- `backend/src/abacus_tools/quality/banned_patterns.py`: only if the proposal's read of last year's items needs a LIST-001 entry (it's authorised by `roll_forward.read` on that engagement);
- `backend/tests/unit/**`.

Not touched: `api/app.py` (existing routers), `identity/authz/__init__.py`, evidence, connections.

### Questions for approval
- **D1. Engagements runs the creation in one unit of work, and requests plugs in the item proposal and copy through a registration hook (ADR-106)?** *Recommendation: yes.* It keeps "what they confirm is exactly what's created" without reversing the module dependency.
- **D2. Add `add_rolled_forward_member` in `identity/service.py` (exported from `identity/api.py`), authorised by the creation, re-checking active, staff and not walled?** *Recommendation: yes.* This is the identity change, named per your TASK-040 amendment.
- **D3. Add the matrix action `roll_forward.read`, held by firm administrators and practice leaders, checked on the prior engagement so walls apply?** *Recommendation: yes.*
- **D4. The creator stays an engagement partner, as today, and isn't listed in the proposed team; last year's partners are proposed as partners alongside?** *Recommendation: yes.* An engagement may have more than one partner. Whoever's confirmed can step back on People.
- **D5. Tick "new in the template" items by default (flagged), while last year's unused items stay unticked?** *Recommendation: yes.* New template items are the firm's current methodology. Untick to drop them.
- **D6. Match template additions to last year's items by area and description, ignoring case and spacing?** *Recommendation: yes.* Items don't record which template item they came from, and adding that link would be a further schema change for little gain now.
- **D7. Write the approval file for the paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — Design written for founder review after TASK-047 (#83) and the template-version fix (#84) merged.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
