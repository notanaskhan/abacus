---
id: SPEC-002
title: Ethical walls
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-026, ADR-020, ADR-023, ADR-024, ADR-025, ADR-027, ADR-007, ADR-031]
related_specs: [SPEC-000]
created: 2026-10-07
updated: 2026-10-07
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
A firm admin can wall a person off from a client: from then on, that person can see and do nothing on any of that client's engagements, present or future, whatever their role. This is the first platform primitive of Phase 1 §5.3, and the one that gates the first real firm: production refuses to start until walls exist (`WALL_SAFE`, founder decision 2026-10-06).

## 2. Problem and context
Audit firms must keep people with a conflict (an independence issue, a personal relationship, or work for a competitor) away from a client's confidential data. Today `authorise` ignores the matrix's `walled: deny` condition and `visible()` filters by role only. A firm admin, practice leader or quality partner sees everything in their scope, and nothing can exclude one person from one client. ADR-026 decides how walls work; this spec makes them real.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Firm admin | Creates and removes walls (fresh MFA), and lists them |
| Any firm user | May be walled off; then denied everywhere on that client |
| Agents and system runs | Act for a person (ADR-025); a wall on that person stops them too |

## 4. Goals and non-goals
**Goals**
- Wall a user off from a client: every engagement of that client, now and later.
- Walls override every role, including firm admin, practice leader and quality partner (ADR-026).
- Enforced in `authorise` (before roles) and in `visible()` (every list), on the next request after the change.
- Create and remove need `firm_admin` with fresh MFA, and both are audited.
- `WALL_SAFE` becomes true, so production may start.

**Non-goals**
- Independence-conflict rules between engagement types (they arrive with the CAS product, ADR-026).
- An admin screen. This spec is API only; the SPA gets walls with the collaboration UI.
- Walls on client users (there are no client users yet).
- Partial walls (one engagement, or read-only access).

## 5. User stories and acceptance criteria
### Story 1: As a firm admin I want to wall a person off from a client, so that a conflicted person can't see or touch that client's work
- **AC-1** Given a firm admin with MFA in the last 15 minutes, when they create a wall for user U and client C, then the wall exists, `wall.created` is audited, and U is walled from the next request.
- **AC-2** Given a firm admin without recent MFA, or anyone else, when they try to create a wall, then they get 403 and nothing changes.
- **AC-3** Given a wall for U and C, when the admin creates the same wall again, then they get 409 `wall_exists`.

### Story 2: As a walled person I can't reach the client's work in any way
- **AC-4** Given U is walled from C, when U calls any engagement-scoped route for an engagement of C, then the response is 404, whatever U's role: engagement partner, firm admin, practice leader or quality partner. It is not 403, so the engagement's existence isn't revealed.
- **AC-5** Given U is walled from C, when U lists engagements (or any list filtered by `visible()`), then nothing of C appears.
- **AC-6** Given a new engagement is later created for C, then U is walled from it too.
- **AC-7** Given U is walled from C, when an agent run or system run acts for U (as initiator or `on_behalf_of`) on an engagement of C, then its next authorised step is denied (layer `wall`) and the run ends as failed.
- **AC-8** Given U is walled from C, then U's access to other clients is unchanged.

### Story 3: As a firm admin I can lift a wall and see who is walled
- **AC-9** Given a wall, when a firm admin with recent MFA removes it, then `wall.removed` is audited, and from the next request U's access follows their roles again.
- **AC-10** Given walls in the firm, when a firm admin lists them, then they see each wall's user, client, creator and creation time. No one else may list walls (403).

### Story 4: Production may start
- **AC-11** Given walls are enforced (AC-4 to AC-8 pass), then `WALL_SAFE` is true and `create_app` starts in production.

## 6. Behaviour and flows
**Happy path**
1. A firm admin with recent MFA calls `POST /v1/walls {user_id, client_id}`.
2. `authorise(ctx, "wall.create", firm)` runs, and the wall row is inserted in a unit of work with `wall.created`.
3. On U's next request, layer 2 of `authorise` finds the wall for the resource's client and denies (layer `wall`). `visible()` adds `client_id NOT IN (U's walled clients)`.

**Alternate paths**
- Removing a wall marks it removed (it is not deleted; the history stays) and audits `wall.removed`.
- Walling a user who isn't a member of the firm → 404. Walling the firm admin themself is allowed.

**State transitions**
| From | Event | To | Who can trigger |
|---|---|---|---|
| (none) | create | active | firm admin, fresh MFA |
| active | remove | removed | firm admin, fresh MFA |

## 7. Domain and data changes
- New table `ethical_walls`:
  - columns: `tenant_id`, `id`, `user_id`, `client_id`, `status` (active|removed), `created_by`, `created_at`, `removed_by`, `removed_at`;
  - one active wall per (tenant, user, client);
  - forced RLS; insert plus update of the status columns only (forward-only: active → removed);
  - owned by identity (walls are an authorisation fact).
- `Resource` learns the engagement's `client_id`, so `authorise` can check walls without another query per call. `engagements.get_ref`/`lock_ref` already load the engagement.
- The glossary gets "ethical wall" (if missing).

## 8. Interfaces
| Method | Path | Action | Notes |
|---|---|---|---|
| POST | /v1/walls | wall.create | `{user_id, client_id}` → 201 WallOut |
| DELETE | /v1/walls/{wall_id} | wall.remove | 204 |
| GET | /v1/walls | wall.read | list (new matrix action, firm admin only; see Q2) |

## 9. Authorisation and tenancy
- **Order:** in `authorise`, layer 2 checks walls before roles (ADR-026). A walled actor is denied whatever the matrix says; the denial logs layer `wall` and the route answers 404.
- **Lists:** `visible()` filters every list by the caller's walled clients, through the engagement's `client_id`.
- **Agents and system contexts:** checked against their initiator / `on_behalf_of` person, live, on every authorised step (ADR-025).
- **Tenancy:** walls are tenant-scoped; RLS applies.
- **Matrix:** add `wall.read: {firm_admin: allow, mfa_recent: required}`. This is a protected change, so it needs approval.

## 10. AI behaviour
N/A: no model calls. Agents are stopped by AC-7.

## 11. Integrations
None.

## 12. Edge cases and failure modes
- **Concurrency:** a wall created while U has a request in flight takes effect on U's next request (ADR-026: "next request").
- **Running workflows:** a run already acting for U is denied at its next activity (AC-7), and the run ends failed with `forbidden`.
- **Removed users:** a removed membership already denies everything; walls add nothing there.
- **Several walls:** the union applies.

## 13. Security and privacy
- 404 rather than 403 on walled engagements, so they aren't disclosed.
- Wall creation and removal are firm-admin only, with fresh MFA, and audited.
- The wall list is sensitive (it reveals conflicts): firm admin only, never in logs beyond IDs.

## 14. Audit trail and evidence integrity
`wall.created` and `wall.removed` audit events, with actor, target wall, and user and client IDs as refs. Wall rows are never deleted.

## 15. Observability
Denials log `authz.denied` with layer `wall` (IDs only). Span attributes are unchanged.

## 16. Performance and scale
One indexed lookup per request: the caller's walled client IDs, cached for the request. The `visible()` filter adds one `NOT IN`.

## 17. UX
No UI in this spec (API only). The SPA shows walled engagements as not found, which is the existing 404 handling.

## 18. Test plan
- **Matrix:** every role, including firm admin, practice leader and quality partner, is denied on a walled client's engagements, for every engagement-scoped action. The test is generated from the matrix (ADR-027).
- **Lists:** every list route excludes the walled client.
- **Agents and system runs:** denied at the next activity, and the run fails.
- **Database:** RLS, forward-only status, one active wall per pair.
- **Startup:** `WALL_SAFE` is true and production startup is allowed.

## 19. Rollout
Behind no flag: walls apply as soon as they exist, and none exist until an admin creates one. Flip `WALL_SAFE` in the same change.

## 20. Open questions
None. Answered by the founder on 2026-10-07 (all recommendations):
- **Q1:** walled engagements answer 404.
- **Q2:** add the matrix action `wall.read` (firm admin, fresh MFA).
- **Q3:** runs already acting for a newly walled person are stopped at their next step.
- **Q4:** API only; the admin screen comes with the collaboration UI spec.

## 21. Future / explicitly deferred
- Independence-conflict policy between engagement types (CAS).
- Client-user walls.
- Notifications to the engagement team when someone is walled.
