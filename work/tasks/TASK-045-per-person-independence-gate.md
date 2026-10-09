---
id: TASK-045
title: Per-person independence gate in authorisation
spec: SPEC-025
acceptance_criteria: [AC-7]
risk_zone: red
status: awaiting-plan-approval
branch: task-045-independence-gate
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
The per-person half of SPEC-025 AC-7, as amended by the founder:
- each team member's own access to client data opens only once they confirm their independence for that engagement;
- adding someone later restricts that person, not the engagement.

## Scope
SPEC-025 AC-7 (per person), plus the screens' handling of it (AC-9).

## Context to load
- Spec: `docs/specs/SPEC-025-act-1-the-engagement-opens.md`; ADR-020, ADR-023, ADR-025, ADR-026, ADR-027, ADR-106
- Code:
  - `identity/authz/__init__.py` (`authorise`, `visible`, `visible_items`, the walls layer and its per-request cache);
  - `identity/authz/matrix.py` (`Rule`, `_MODIFIERS`);
  - `abacus_tools/codegen/permission_matrix.py`;
  - `engagements/setup.py` and `independence_confirmations`;
  - `apps/web` `EngagementLayout`.

## Plan
- [ ] Plan approved by human

### Why this is in `identity/authz` (as discussed in TASK-044 D1)
Every read and list of client data passes through `authorise` or `visible()`. A check in each service would miss the list queries (the Board's evidence, the review queue, screening results, the access log) and anything built later. Walls are enforced the same way.

### Design (for founder review)
1. **A new matrix modifier, `independence: required`** (in `authz/matrix.py`):
   - `Rule` gains `independence: bool`;
   - the parser accepts the key, and the codegen writes it into `_matrix.py`;
   - it's a separate key, so `requires: reason` keeps its meaning.
2. **Marked actions** (in `permission-matrix.yaml`, D1):
   - `evidence.read` and `evidence.upload`;
   - `evidence.accept` and `evidence.reject` (send back uses reject);
   - `review.read`, `review.take` and `review.assign`;
   - `screening.request`;
   - `connection.read_log`.

   Not marked: request items, the setup, team and contacts. An unconfirmed person still sees what the engagement is and what's asked, but not the client's data.
3. **A new layer in `authorise`, "independence"**, after roles:
   - it applies when the rule is marked, the actor is a person (`AuthContext`, not break-glass support), and the role that grants the action is a staff engagement role;
   - it denies unless that person has confirmed for that engagement.
   - **Not affected:**
     - client roles (clients aren't bound by the firm's independence);
     - platform support (break-glass has its own controls, ADR-028);
     - system runs.
   - **Agents are covered:** the existing initiator intersection (ADR-025) re-runs `authorise` for the person the agent acts for, so an unconfirmed person's agent is refused too.
   - The layer name is `independence`. It's logged, never shown to the caller, as with every layer.
4. **Who answers "has this person confirmed?" (D2):**
   - engagements registers two functions through a registration slot (ADR-106), as it does for the engagement's client for walls:
     - a lookup `(tenant, engagement_id, user_id) -> bool` for `authorise`;
     - a column expression `(engagement_id_column, user_id) -> EXISTS(confirmed)` for `visible()`;
   - **unregistered means denied** (fail closed), as walls are;
   - lookups are cached per request with the walls cache (`recording_checks`).
5. **`visible()` and `visible_items()`:** for marked actions, the staff-role membership filter also requires a confirmed confirmation for the same engagement and person. Client reach in `visible_items` is unchanged.
6. **Web:**
   - when the signed-in person's own confirmation on an engagement isn't `confirmed`, the engagement shows a banner: "Confirm your independence to see client data", with Confirm (and "I can't confirm" with a note);
   - the client-data tabs (Requests evidence, Review, item detail) show that message instead of a generic "not allowed";
   - the confirmation comes from `GET …/setup`, which stays readable.
7. **Tests:**
   - the matrix tests gain the modifier;
   - the permission tests cover the layer: confirmed allowed; requested and declined refused; client roles, support and system unaffected; an agent of an unconfirmed person refused; unregistered refused;
   - `visible()` gets SQL-shape tests;
   - a local smoke checks someone added later is refused evidence until they confirm.

**Protected paths (approval file), each named:**
- `backend/src/abacus/modules/identity/authz/__init__.py`: the layer, the registration slot, `visible()`;
- `backend/src/abacus/modules/identity/authz/matrix.py`: the modifier;
- `backend/src/abacus/modules/identity/authz/_matrix.py`: generated;
- `backend/src/abacus/modules/identity/*` (top-level only): exporting the registration function from `api.py`;
- `docs/architecture/permission-matrix.yaml`: marking the actions;
- `backend/tests/unit/**`.

Not protected but changed: `abacus_tools/codegen/permission_matrix.py`, `engagements`, `apps/web`.

Not touched:
- `schema_check.py` (no schema change);
- `api/app.py`;
- evidence, connections and agents (they already call `authorise` and `visible()`).

### Questions for approval
- **D1. Mark exactly these actions:**
  - evidence read and upload;
  - accept and reject;
  - review read, take and assign;
  - "Screen now";
  - the connection access log.

  Request items, setup, team and contacts stay visible to an unconfirmed member. *Recommendation: yes.*
- **D2. Engagements answers "confirmed?" through a registration slot in `authz`, failing closed when unregistered, cached per request like walls?** *Recommendation: yes.*
- **D3. Client roles, platform support (break-glass) and system runs are outside the independence layer; agents are covered through their initiator?** *Recommendation: yes.*
- **D4. Write the approval file for the paths above, including `identity/authz/__init__.py` and `authz/matrix.py`?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — Design written for founder review after TASK-044 merged (#80).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
