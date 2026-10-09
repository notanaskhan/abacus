---
id: TASK-042
title: Autonomy policy and the onboarding checklist
spec: SPEC-024
acceptance_criteria: [AC-5, AC-7, AC-8]
risk_zone: red
status: done
branch: task-042-autonomy-checklist
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
The last Act 0 task (SSO aside):
- the firm's autonomy level, stored and enforced where the platform acts on its own today;
- the onboarding checklist that walks a new firm administrator to their first engagement.

## Scope
SPEC-024 AC-5, AC-7 and AC-8 (for these screens). SSO (AC-2) stays held; the checklist's SSO step says so.

## Context to load
- Spec: `docs/specs/SPEC-024-act-0-the-firm-gets-ready.md`; ADR-061, ADR-005
- Code:
  - `firms` (identity), `identity/staff.py`, walls;
  - `connections/auto_retrieval.py`;
  - `agents/screenings.py` (`start_screening`) and `agents/service.py` (`create_screening_run`);
  - `engagements` (templates, engagements, `firm_router`);
  - `apps/web` `AdminLayout`, `Budget`, `Walls`, `Engagements`.

## Plan
- [x] Plan approved by human (founder, 2026-10-09: D1–D4). Approved by founder: paths listed under *Protected paths*, plus the generated `identity/authz/_matrix.py` (added by the founder when the matrix change needed it; generator output only, no hand edits). I ran the generator once before asking, then reverted it, asked, and regenerated after approval.

### What the code shows
- **Two things happen automatically today:**
  - **automatic retrieval:** after a client connects, or an item becomes A (behind the `retrieval.auto` flag);
  - **screening:** of every new retrieved version, through the `evidence_version.created` subscription.
- **Nothing lets a person start screening.** `screening.run` belongs to the system and the agent.
- **The matrix already has `autonomy_policy.update`** (firm admin, fresh MFA). Nothing stores a level yet.

### Design (for founder review)
1. **Firm settings (migration 0034, identity):**
   - `firms` gains `autonomy_level` (0 to 3, default 1), `autonomy_set_at`, `budget_reviewed_at`, `walls_none_needed_at`, `sso_skipped_at` and `onboarding_dismissed_at`;
   - the app may update exactly these columns of its own firm (forced RLS); nothing else on `firms` changes.
2. **Autonomy (Q3, Q4):**
   - **Read:** `GET /v1/firm/autonomy` (`firm.read_settings`, a new read action for firm administrators and practice leaders, without fresh MFA, D1).
   - **Set:** `PUT /v1/firm/autonomy` (`autonomy_policy.update`, fresh MFA), audited `autonomy_policy.updated`.
   - Levels 2 and 3 are refused with 409 `level_not_available` ("comes with the engagement agent").
   - `identity.api.autonomy_level(tenant)` is read fresh at each automatic action.
   - **Enforcement at Level 0 (Advise):**
     - the automatic-retrieval subscriber does nothing (logged `auto_retrieval.skipped`, reason `advise`);
     - the screening subscriber records no run (logged `screening.skipped`, reason `advise`).
   - At Level 1, today's behaviour. The `retrieval.auto` flag stays as the operator's kill switch.
3. **"Screen now" (D1):**
   - at Advise, a person starts screening on a version from the item page: `POST /v1/engagements/{id}/evidence-versions/{version_id}/screen`;
   - this dispatches the same screening workflow, requested by that person, once per version (a running or finished screening is answered, not repeated);
   - it needs a new matrix action `screening.request` for the engagement partner, manager, senior and staff (the people who can already retrieve). The agent still decides nothing (ADR-005).
4. **The checklist** (`GET /v1/firm/onboarding` with `firm.read_settings`; `POST /v1/firm/onboarding/dismiss` with `firm.manage_settings`; engagements module, which reads identity's firm facts through its API, D2). Every step is computed from data, never stored:

   | Step | Done when |
   |---|---|
   | Single sign-on | Shows "Coming soon" with "Skip for now" (`sso_skipped_at`) while SSO is held |
   | Invite your team | Another active staff member exists, or an invitation is pending |
   | Upload your methodology | Any template version exists |
   | Set autonomy | `autonomy_set_at` is set (the admin chose, even if they kept Routine) |
   | Review your AI budget | A budget was set, or "Looks right" was clicked (`budget_reviewed_at`) |
   | Ethical walls | A wall exists, or "None needed" was clicked (`walls_none_needed_at`) |
   | Create your first engagement | Any engagement exists |

   The admin can also dismiss the checklist (`onboarding_dismissed_at`). Small actions acknowledge a step (`POST /v1/firm/onboarding/{step}/acknowledge` for `sso`, `budget` and `walls`, `firm.manage_settings`, fresh MFA), audited.
5. **Web:**
   - **Checklist:** the first thing a firm administrator sees, at `/` above the engagements list and also `/admin/setup`. It shows progress ("4 of 7 done"), each step with a link to its screen, and Dismiss. It hides when done or dismissed.
   - **Autonomy tab** in Firm admin: four levels in plain words (what the agent may and may not do), Advise and Routine selectable, Manage and Portfolio marked "Coming with the engagement agent", and "Confirm it's you" on save.
   - **Budget:** gains "Looks right". **Walls:** gains "None needed".
   - **Item page:** "Screen now" on an unscreened version when the firm is at Advise.

**Protected paths (approval file):**
- `backend/src/abacus/modules/identity/*` (firm settings, `autonomy_level`; `identity/authz` untouched);
- `backend/src/abacus/modules/connections/**` (the auto-retrieval check);
- `backend/src/abacus/modules/agents/**` (the screening check and "Screen now");
- `docs/architecture/permission-matrix.yaml` (`screening.request` and `firm.read_settings`, D1);
- `backend/src/abacus_tools/quality/schema_check.py` (the `firms` update grant);
- `backend/src/abacus_tools/quality/banned_patterns.py` (if needed);
- `backend/tests/unit/**`.

Checked and not needed:
- `api/app.py`: onboarding routes go on the existing engagements `firm_router`, and autonomy on the identity router;
- evidence: no change;
- engagements: not protected.

### Questions for approval
- **D1. Add two matrix actions?** *Recommendation: yes.*
  - `screening.request` (engagement partner, manager, senior, staff), so people can start screening at Advise. Otherwise Level 0 would mean no screening at all.
  - `firm.read_settings` (firm administrator, practice leader, no fresh MFA), so the checklist and autonomy can be viewed without a fresh sign-in; changes still need one.
- **D2. The checklist lives in engagements (methodology and engagement facts) and reads identity's firm facts (staff, invitations, walls, settings) through its API, so no new module and no boundary change?** *Recommendation: yes.*
- **D3. "Set autonomy" counts as done once the admin opens the screen and saves, even if they keep Routine, so the default is a conscious choice?** *Recommendation: yes.*
- **D4. Write the approval file for the paths above?** *Recommendation: yes.*

## Definition of done
- [x] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [x] Type check, lint, format, architecture and dependency rules pass
- [x] Every query is tenant-scoped; every endpoint checks authorisation
- [x] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — Implemented:
  - migration 0034 (`firms` autonomy and onboarding columns, with an app update grant on exactly those);
  - the autonomy read and set routes;
  - Advise checks in automatic retrieval and screening; "Screen now" (`screening.request`);
  - the onboarding service and routes;
  - the matrix's `firm.read_settings` and `screening.request`;
  - the checklist (on the engagements page and in Firm admin → Setup), the Autonomy tab, "Looks right" on Budget, "None needed" on Walls and "Screen now" on the item page.

  Saving a budget also marks the budget step (`identity.note_budget_reviewed`, in the same unit of work), because engagements can't read the gateway's budgets.

  Tests and checks:
  - backend unit 9,067 and web 177 passed; the gates pass; migration 0034 applies, rolls back and reapplies;
  - a local smoke passed: a new firm showed 0 of 7 steps at Routine; Advise was set and level 2 refused; acknowledgements ticked SSO, budget and walls; at Advise the screening subscriber dispatched nothing. The smoke firm was removed.
- `2026-10-09` — Design written for founder review after TASK-041 merged (#76).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
