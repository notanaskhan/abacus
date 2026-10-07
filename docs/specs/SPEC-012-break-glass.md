---
id: SPEC-012
title: Break-glass support access
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-028, ADR-007, ADR-014, ADR-020, ADR-024, ADR-036, ADR-098]
related_specs: [SPEC-002]
created: 2026-10-07
updated: 2026-10-07
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
ADR-028 says platform staff have no standing access to customer data. Support uses break-glass sessions instead:
- time-limited;
- requiring a stated reason;
- visible to the firm;
- fully audited.

This spec builds the application side:
- staff request a session for one firm;
- the firm approves it (or, in an emergency, two staff approve it and the firm is told at once);
- during the session, a staff member can read through the API as a read-only `platform_support` role;
- every request in the session is audited in the firm's own audit trail;
- the session ends by expiry or revocation.

A quarterly access-review report supports SOC 2.

Time-bound infrastructure roles for the database and storage (also in ADR-028) are Terraform, so they come with TASK-014.

## 2. Problem and context
- **Today** no staff member can see a firm's data through the product. That is correct, but support has no path at all, so the only way to diagnose a firm's problem would be direct database access, which ADR-028 forbids.
- **What firms need:** due-diligence questionnaires ask who at the vendor can see client data, when, and how the firm knows. We need a precise, auditable answer.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Platform staff (support) | Request a session with a reason; read during it |
| A second staff member | Approves an emergency session (Q1) |
| Firm admins | Approve, see and revoke sessions; see every access in their audit trail |
| The platform | Enforces the time limit, read-only access and auditing |

## 4. Goals and non-goals
**Goals**
- **Staff identities are separate (Q4):** a staff token from the platform's own issuer, with the `staff` claim and MFA, and never a membership in any firm.
- **Sessions:**
  - `support_sessions` (tenant-scoped) records the requester, reason, scope, requested window, approvals, start, expiry, end and status;
  - the maximum length is 4 hours (Q3).
- **Approval (Q1):**
  - normal sessions: a firm admin with fresh MFA approves;
  - emergency sessions: a second staff member approves, the session lasts at most 1 hour, and the firm is told immediately (an audit event, plus a banner flag on the firm's session list; email waits for notifications).
- **Access during a session (Q2):**
  - requests carry the staff token plus `X-Support-Session`, and become a `SupportContext`;
  - `authorise` treats it as the read-only role `platform_support` on that firm only;
  - the matrix grants `platform_support` read actions only, never `*.create`, decisions, uploads, exports or flags, and never content unless the session's scope is `content`.
- **Auditing:**
  - every request in a session writes `support.request` (route template and method, never parameters or bodies) in the firm's audit trail, with actor kind `support`;
  - opening, approving, revoking and expiry are audited too.
- **Firm visibility:** `GET /v1/support-sessions` lets firm admins see past and current sessions; `POST …/{id}/revoke` ends one at once.
- **Access review:** `make access-review QUARTER=2026Q4` writes a report of every session in every firm (who, firm, reason fingerprint, scope, approvals, length, request count) for the quarterly SOC 2 review.

**Non-goals**
- **Write access for support:** there is none, ever. Fixes go through code or firm users.
- **Infrastructure:** time-bound IAM and database roles, and alarms on their use (TASK-014, Terraform).
- **A staff console UI:** API and CLI only in v1.
- **Email or in-app notifications:** these come with the notifications primitive. Until then the firm sees sessions in its list and audit trail.

## 5. User stories and acceptance criteria
### Story 1: Support asks; the firm decides
- **AC-1** Given a staff member, when they request a session for a firm with a reason (20 to 1,000 characters), a scope (`metadata` or `content`) and a duration (at most 4 hours), then a `requested` session is recorded and `support_session.requested` is audited in the firm's trail. Nothing is accessible yet.
- **AC-2** Given a requested session, when a firm admin with fresh MFA approves it, then it becomes `active` from that moment until the requested duration ends, and `support_session.approved` is audited. Anyone else (another role, stale MFA, another firm) is refused.
- **AC-3** Given an emergency request (Q1), when a different staff member approves it, then it becomes `active` for at most 1 hour, `support_session.emergency_approved` is audited, and the firm's session list marks it as an emergency until a firm admin acknowledges it. The requester can never approve their own request.

### Story 2: Read-only, scoped, time-boxed
- **AC-4** Given an active session, when the staff member calls a read route with their staff token and `X-Support-Session`, then the request is authorised as `platform_support` on that firm only. Read actions in the matrix succeed. Content reads succeed only with scope `content`.
- **AC-5** Given any write route, any decision, upload, export or flag change, or another firm's resource, then the request is refused (403), even during an active session. Agents and system contexts never take the `platform_support` role.
- **AC-6** Given a session past its expiry, revoked, or not yet approved, then every request with it is refused (401, `support_session_inactive`). Expiry is checked on each request, and no grant outlives its expiry.
- **AC-7** Given a staff token without a session header, or with another staff member's session, then it is refused. Staff have no standing access (ADR-028).

### Story 3: Everything is visible
- **AC-8** Given any request under a session, then `support.request` is audited in the firm's trail (actor kind `support`, the staff ID, the session ID, the route template and method, never parameters). A request that can't be audited is refused (fail closed).
- **AC-9** Given a firm admin, when they list sessions, then they see every session for their firm (requester, reason, scope, window, approvals, status, request count), and they can revoke an active one, which takes effect on the next request.
- **AC-10** Given `make access-review QUARTER=…`, then a report lists every session in the quarter across firms, with the reason as a fingerprint (the text stays in the firm's trail) and counts. It is written to `docs/operations/access-reviews/<quarter>.json` for the SOC 2 record.

## 6. Behaviour and flows
1. **Request:** staff call `POST /v1/support/sessions` (staff token) with the firm, reason, scope, duration and emergency flag. It is recorded and audited in the firm's tenant.
2. **Approve:**
   - normal: a firm admin calls `POST /v1/support-sessions/{id}/approve` (fresh MFA);
   - emergency: a second staff member calls `POST /v1/support/sessions/{id}/approve`.
3. **Use:**
   - each request with the staff token and `X-Support-Session` loads the session in that firm's tenant, checks it is active and belongs to this staff member, and builds a `SupportContext`;
   - `authorise` applies the `platform_support` row, and the route's own action check still runs;
   - `support.request` is audited.
4. **End:** at expiry, or when the staff member (`POST /v1/support/sessions/{id}/end`) or a firm admin (`…/revoke`) ends it.

## 7. Domain and data changes
- **`support_sessions`** (tenant-scoped, forced RLS):
  - columns: `id`, `tenant_id`, `staff_id`, `reason`, `scope` (`metadata` or `content`), `duration_minutes` (at most 240), `emergency`, `status` (`requested`, `active`, `ended`, `revoked`, `expired`), `approved_by_kind` (`firm_admin` or `staff`), `approved_by`, `starts_at`, `expires_at`, `ended_at`, `acknowledged_at`, `created_at`;
  - UPDATE is granted only on the status and lifecycle columns.
- **`audit_events.actor_kind`** gains `support`.
- **The matrix** gains the role `platform_support` (read actions only, with content reads conditional on scope). This is a protected change.
- **Settings:** `staff_issuer`, `staff_audience` and `staff_jwks` (the staff identity provider; locally the fake issuer).

## 8. Interfaces
| Interface | Purpose |
|---|---|
| `POST /v1/support/sessions`, `POST /v1/support/sessions/{id}/approve` and `…/end` | Staff (staff token) |
| `GET /v1/support-sessions`, `POST /v1/support-sessions/{id}/approve` and `…/revoke` and `…/acknowledge` | Firm admins (`support_session.manage`, fresh MFA for approve) |
| `X-Support-Session` header | Staff reads during an active session |
| `make access-review QUARTER=…` | The quarterly report |

## 9. Authorisation and tenancy
- **New matrix entries (a protected change):**
  - the role `platform_support`;
  - the action `support_session.manage` (firm admin, `mfa_recent` for approval).
- **Tenancy:** a `SupportContext` is bound to one tenant, from the session row, never from the request. Staff tokens carry no tenant.
- **Walls:** ethical walls (SPEC-002) still apply to support reads. A walled client's engagements stay hidden unless a firm admin approves a session whose scope names them, which is deferred, so walls always apply in v1.

## 10. AI behaviour
None. Agents can never hold the support role.

## 11. Integrations
The staff identity provider (the vendor's separate staff organisation, with MFA), configured with TASK-014. Locally and in CI, the fake issuer signs staff tokens.

## 12. Edge cases and failure modes
- **A session expires mid-request:** the request was authorised at its start. The next request is refused.
- **Audit write failure:** the request is refused (AC-8).
- **Clock skew:** expiry uses database time.
- **A firm admin who is also staff:** staff tokens and firm tokens come from different issuers, so roles never mix.
- **Overlapping sessions:** one active session per staff member per firm at a time.

## 13. Security and privacy
- **Least privilege:** read-only, one firm, time-boxed, scope-limited.
- **No standing access:** a staff token alone opens nothing.
- **The reason is free text**, so it stays in the firm's trail and session row and is fingerprinted in reports. It is never logged.
- **Two-person rule** for emergencies.
- **Everything is visible to the firm.**

## 14. Audit trail and evidence integrity
The audited events are:
- `support_session.requested`, `support_session.approved`, `support_session.emergency_approved`, `support_session.acknowledged`, `support_session.revoked`, `support_session.ended` and `support_session.expired`;
- one `support.request` per request.

All are in the firm's trail.

## 15. Observability
- **Metrics:** active sessions, requests under sessions, refusals by reason.
- **Alert:** any emergency session (to operators).

## 16. Performance and scale
One session lookup per support request. Sessions are rare.

## 17. UX
None beyond the firm admin API in v1. A sessions panel comes with the admin UI.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-3 | integration | Request, firm approval (MFA), emergency two-person approval, self-approval refused |
| AC-4 to AC-7 | integration + generated matrix tests | Read allowed; content only with scope; writes refused; inactive, expired or foreign sessions refused |
| AC-8 | integration | Per-request audit; an audit failure refuses the request |
| AC-9, AC-10 | integration + unit | Firm list and revoke; access-review report |

## 19. Rollout
The migration is additive and extends the actor kind. Until staff identities exist (TASK-014), only local and CI use the fake staff issuer.

## 20. Open questions
None. Answered by the founder on 2026-10-07 (all recommendations):
- [x] **Q1: approval.** *Recommendation:* a firm admin with fresh MFA approves normal sessions. Emergency sessions need a second staff member, last at most 1 hour, and are flagged to the firm until a firm admin acknowledges them.
- [x] **Q2: what support can read.** *Recommendation:*
  - read actions only;
  - `metadata` scope sees structure (engagements, items, statuses, runs, usage);
  - `content` scope adds evidence and screening content;
  - walls always apply;
  - never any write, decision, export or flag change.
- [x] **Q3: duration.** *Recommendation:* at most 4 hours, ended early by the staff member or a firm admin, with one active session per staff member per firm.
- [x] **Q4: staff identity.** *Recommendation:* a separate issuer for staff (the identity vendor's staff organisation, with MFA), configured with TASK-014, and the fake issuer locally. Staff are never members of a firm.
- [x] **Q5: access review.** *Recommendation:* `make access-review QUARTER=…` writes a JSON report with reasons fingerprinted, committed under `docs/operations/access-reviews/`. The founder signs off each quarter in the commit.

## 21. Future / explicitly deferred
- Time-bound infrastructure roles and their alarms (TASK-014).
- Email and in-app notification of sessions.
- A staff console.
- Wall-scoped support sessions.
- Session recording beyond per-request audit.
