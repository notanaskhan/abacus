---
id: SPEC-014
title: Firm-level reads for engagement roles
status: draft
owner: founder
risk_zone: red
related_adrs: [ADR-020, ADR-024, ADR-027, ADR-102]
related_specs: [SPEC-008, SPEC-009]
created: 2026-10-08
updated: 2026-10-08
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Some actions concern the firm as a whole, not one engagement: reading methodology templates and searching knowledge. The permission matrix grants them to engagement roles too, for example:
- `methodology.read` to engagement partners and managers;
- `knowledge.read` to partners, managers, seniors, staff and reviewers.

But `authorise` on a firm-level resource only looks at the user's firm role, so people with engagement roles only are refused. That is the known limitation recorded in TASK-023 and TASK-024.

**The fix:** for firm-level read actions, an engagement role counts if the user currently holds it on at least one active (not archived) engagement in the firm. It applies only where the matrix says `allow`.

## 2. Problem and context
**What breaks today:**
- Most of a firm's people hold engagement roles only. A senior on two audits can't search the firm's methodology knowledge.
- A manager can't list the templates they need to pick one to apply to their engagement.

**The rule we need:** the matrix already says who should be allowed. `authorise` just can't evaluate engagement roles without an engagement, so it needs a precise rule for that case.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Engagement-only users | Gain the firm-level reads the matrix already grants them |
| `authorise` | Evaluates engagement roles on firm resources by the new rule |

## 4. Goals and non-goals
**Goals**
- **The rule:** on a firm-level resource (`Resource.firm`), for a **read** action, the user's roles are their firm role (if any) plus every engagement role they hold on a non-archived engagement of the firm. The matrix decides with those roles as usual, and an explicit `deny` still wins.
- **Scope of the rule:**
  - only `allow` counts for engagement roles at firm level;
  - conditional decisions (`in_scope`, `client_visible_only`, `assigned_only`, `firm_setting(...)`) never grant at firm level, because they only make sense for one engagement;
  - write actions on firm resources are unchanged: firm roles only.
- **Caching:** the role lookup is cached per request, like walls.
- **Generated tests:** the matrix tests gain the firm-level rule, so every firm-level read is tested for engagement-only users.

**Non-goals**
- Changing any matrix decision.
- Firm-level writes for engagement roles.
- Engagement-level authorisation, which is unchanged.
- `visible()`. The firm-level list queries (templates, knowledge) are firm-wide and already exempt.

## 5. User stories and acceptance criteria
- **AC-1** Given a user with no firm role who is a senior on an active engagement, when they search knowledge (`knowledge.read`, firm resource), then it is allowed.
- **AC-2** Given a user who is a manager on an active engagement, when they list methodology templates (`methodology.read`), then it is allowed. A senior (not granted by the matrix) is refused.
- **AC-3** Given a user whose only engagement memberships are on archived engagements, or who has none, then firm-level reads granted only to engagement roles are refused.
- **AC-4** Given a firm-level **write** action whose matrix row allows an engagement role (none exist today; tested with a probe rule), then an engagement-only user is still refused. The rule is reads only.
- **AC-5** Given an engagement role whose firm-level decision is conditional (for example `in_scope`), then it doesn't grant at firm level.
- **AC-6** Given agents and system contexts, then nothing changes. They never act on firm-level resources.
- **AC-7** Given break-glass support contexts (SPEC-012), then nothing changes. Their roles are the support roles only, and they hold no engagement roles.

## 6. Behaviour and flows
1. **Roles:** `authorise(ctx, action, Resource.firm(t))` collects the roles: the firm role, plus, if the action is a read and the context is a person (not support), `engagement_roles_in_firm(tenant, user)`. Those are the distinct roles on non-archived engagements, from one query, cached per request.
2. **Decision:** the matrix decision is taken as today, with conditional decisions treated as non-grants at firm level.

## 7. Domain and data changes
None. There is one new identity repository query, joining engagement members and engagements, reached through the `register_engagement_client` slot pattern or an identity-owned view (Q2).

## 8. Interfaces
No new routes. `authorise` behaviour changes as above.

## 9. Authorisation and tenancy
This is the change. It is protected and red. The tenant comes from the context, and the query is tenant-scoped.

## 10. AI behaviour
None.

## 11. Integrations
None.

## 12. Edge cases and failure modes
- **A role lookup fails:** fail closed (deny), as other authorise lookups do.
- **A user removed from all engagements:** refused from the next request (no caching beyond the request).
- **A walled user:** walls don't apply to firm-level resources today (methodology and knowledge name no client). That is unchanged.

## 13. Security and privacy
- **Granted only what the matrix says:** the change grants only what the matrix already declares for those roles. Least privilege holds, because conditional decisions don't grant and writes are excluded.
- **Tested both ways:** the generated tests cover every firm-level read for every engagement role, allowed and refused.

## 14. Audit trail and evidence integrity
Unchanged. Allowed and denied decisions are logged as today.

## 15. Observability
Unchanged (`authz.allowed` and `authz.denied` with the layer).

## 16. Performance and scale
One extra small indexed query per request that authorises a firm-level read for a user without a granting firm role. It is cached per request.

## 17. UX
None.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-3 | unit (generated) + integration | Each firm-level read × each engagement role; active versus archived |
| AC-4, AC-5 | unit | A write probe and a conditional probe don't grant |
| AC-6, AC-7 | unit | Agent, system and support contexts unchanged |

## 19. Rollout
No migration and no flag. The behaviour widens only to what the matrix already states.

## 20. Open questions
- [ ] **Q1: which engagements count.** *Recommendation:* any non-archived engagement in the firm where the user holds the role. An archived engagement confers nothing new.
- [ ] **Q2: where the lookup lives.** *Recommendation:* identity's repository reads `engagement_members` (identity's table) joined to `engagements.status` through the existing `register_engagement_client` slot, extended with an `active_engagements` subquery. That respects module ownership (ADR-106), and identity never imports engagements.
- [ ] **Q3: reads only.** *Recommendation:* yes, the rule applies only to read actions (the matrix's read verbs). Firm-level writes stay firm-role-only until a spec needs otherwise.

## 21. Future / explicitly deferred
- Firm-level writes for engagement roles, if ever needed.
- Practice-scoped reads (practice leaders' `in_scope` at firm level).
