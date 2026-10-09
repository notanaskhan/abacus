---
id: SPEC-024
title: "Act 0: the firm gets ready"
status: draft
owner: founder
risk_zone: red
related_adrs: [ADR-002, ADR-005, ADR-014, ADR-020, ADR-026, ADR-029, ADR-030, ADR-061, ADR-069]
related_specs: [SPEC-002, SPEC-007, SPEC-008, SPEC-012, SPEC-015, SPEC-016, SPEC-019]
created: 2026-10-09
updated: 2026-10-09
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
**Act 0 promise:** a firm goes from sign-up to its first engagement in an afternoon, and nothing about its setup needs a call with us.

**Story:** Sam Patel, firm administrator at Whitfield & Lane:
1. signs the firm up and connects its single sign-on;
2. invites the audit team, each person with a role;
3. uploads the methodology, which Abacus checks row by row;
4. makes three decisions: the autonomy level (Routine to start), the monthly AI budget, and the ethical walls.

This spec fills the gaps between that story and what exists:
- self-serve sign-up;
- the firm's SSO connection;
- inviting staff and managing their roles;
- the autonomy policy;
- engagement types with a template each;
- the onboarding checklist that walks Sam through all of it.

## 2. Problem and context
**What exists:**
- **Methodology upload:** validated row by row, with problems named by sheet, row and column (SPEC-008, SPEC-016).
- **Account rules:** map ledger accounts to audit areas (SPEC-008).
- **Budget** (SPEC-007, SPEC-019), **ethical walls** (SPEC-002, SPEC-019) and **support access** (SPEC-012, SPEC-019).
- **Sign-in:** through the identity provider (a local fake now, WorkOS later, ADR-029).

**What's missing:**
- **No sign-up.** A firm and its first administrator exist only through the seed script.
- **No SSO setup.** Sign-in assumes one platform-wide provider. ADR-030 says firm users with an identity provider use SSO, and nothing lets a firm connect theirs.
- **No staff invitations or firm roles.** Only client contacts can be invited (SPEC-015). The matrix has `firm.manage_users`, but no route or screen uses it.
- **No autonomy policy.** ADR-061 sets autonomy per firm (0 Advise, 1 Routine, 2 Manage, 3 Portfolio). The matrix has `autonomy_policy.update`, but nothing stores or applies it.
- **One engagement type** (`audit`), and templates aren't tied to a type, so "a request-list template for each engagement type" can't be expressed.
- **No checklist,** so nothing tells a new firm what to do next.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Firm administrator (Sam) | Signs up; connects SSO; invites and manages people; uploads the methodology; sets autonomy, budget and walls |
| Invited staff | Accept an invitation and sign in (through the firm's SSO once connected) |
| Abacus (code, not a model) | Validates the methodology row by row; maps accounts to areas by the firm's rules |

## 4. Goals and non-goals
**Goals**
- **Sign-up** (`/signup`, Q1):
  - the person signs in with the identity provider (a verified email), then enters the firm's name;
  - Abacus creates the firm (tenant) and makes them its first firm administrator, with the firm's default budget and every setting at its safe default;
  - they land on the onboarding checklist;
  - controls: one firm per sign-up, rate-limited, audited, and gated by Q1.
- **SSO connection** (Settings → Single sign-on, Q2):
  - the admin enters the firm's email domain(s) and connects the identity provider through the identity vendor's admin portal link (WorkOS organisations; the local fake provider stands in until TASK-014);
  - once connected, staff whose email is in the firm's domain must sign in through SSO; other sign-in methods are refused for them (ADR-030);
  - the connection's status shows on the page and the checklist;
  - fresh MFA (`firm.manage_settings`).
- **Users and roles** (Firm admin → People):
  - the firm's staff, with role and status, and pending invitations;
  - **invite:** email, firm role (`firm_admin`, `practice_leader`, `quality_partner` or none), single-use expiring link, delivered as client invitations are (SPEC-015);
  - **change** a person's firm role, **revoke** access (applies on the next request), **resend** or **revoke** an invitation;
  - all through `firm.manage_users` (fresh MFA);
  - the firm always keeps at least one firm administrator.
- **Autonomy policy** (Firm admin → Autonomy, Q3):
  - the firm's level, from ADR-061, with plain words for what the agent may and may not do at each level;
  - new firms start at Routine (Level 1);
  - `autonomy_policy.update` (fresh MFA), audited;
  - the level is enforced where the agent acts today (Q4).
- **Engagement types and templates** (Q5):
  - engagement types `audit`, `review`, `compilation` and `agreed_upon_procedures`;
  - each methodology template is tagged with the types it serves;
  - creating an engagement offers the firm's templates for its type.
- **Onboarding checklist** (shown to firm admins until it's done or dismissed). Each step is ticked automatically from the firm's state and links to its screen:
  1. Connect single sign-on, or choose to skip it (Q2);
  2. Invite your team;
  3. Upload your methodology;
  4. Set autonomy;
  5. Review your AI budget;
  6. Add ethical walls, or mark "none needed";
  7. Create your first engagement.

  It shows how many steps are done.

**Non-goals**
- Billing, plans and payment (the plan limit stays as SPEC-007 defines it).
- SCIM user provisioning from the identity provider.
- Per-engagement autonomy overrides (ADR-061 allows them later).
- Model-based methodology mapping. Mapping stays rule-based (the firm's own rules).

## 5. User stories and acceptance criteria
- **AC-1** Given a signed-in person with a verified email and no firm (and, during the pilot, a valid sign-up code, Q1), when they sign up with a firm name, then the firm is created with them as its only firm administrator, defaults are set, the act is audited, and they land on the checklist. A second attempt with the same code or identity is refused.
- **AC-2** Given a firm administrator with fresh MFA, when they connect SSO for their domain, then the connection's status shows. Afterwards, staff with that domain can sign in only through it, while others (and client users) are unaffected.
- **AC-3** Given a firm administrator with fresh MFA, when they invite a person with a firm role, then a single-use expiring link is sent. When the person accepts it, they become a member with that role. Resend and revoke behave as client invitations do.
- **AC-4** Given a firm administrator, when they change a member's firm role or revoke their access, then it applies on the member's next request and is audited. Removing or demoting the last firm administrator is refused.
- **AC-5** Given a firm administrator with fresh MFA, when they set the autonomy level, then it's stored and audited. A new firm starts at Routine. The agent's current actions follow it (Q4).
- **AC-6** Given methodology templates tagged by engagement type, when someone creates an engagement of a type, then only matching templates are offered.
- **AC-7** Given a new firm, then the checklist shows each step's state from the firm's data, links to each screen, and disappears when everything is done or the admin dismisses it.
- **AC-8** Given every new screen, then loading, empty, error and not-allowed states exist, and colours come only from tokens.

## 6. Behaviour and flows
1. Sam opens `/signup`, signs in with the identity provider, enters "Whitfield & Lane" (and a code, Q1), and lands on the checklist.
2. SSO: Sam enters `whitfieldlane.com` and follows the vendor's portal link back to Abacus, which shows "Connected".
3. People: Sam invites 12 people with roles. Each accepts by signing in through SSO.
4. Methodology: Sam uploads, sees "row 14: tier must be A to E", fixes it and uploads again: version 1.
5. Autonomy (Routine), budget and walls.
6. Sam creates the first engagement. The checklist is done.

## 7. Domain and data changes
- **`firms`** gains `email_domains`, `sso_status`, `sso_connection_ref` (the vendor's organisation ID, not a secret), `autonomy_level` (0 to 3, default 1), `onboarding_dismissed_at`, `walls_none_needed_at`, `created_by`.
- **`staff_invitations`:** as `client_invitations`, with a firm role instead of an engagement role.
- **`signup_codes`** (if Q1 is gated): hashed, single-use, issued by the founder through tooling.
- **`engagements.type`** allows the four types; **`methodology_templates`** gains `engagement_types`.

## 8. Interfaces
- `POST /v1/signup`.
- **Settings:** `GET`/`PUT /v1/firm/settings` (domains, SSO status, autonomy), `POST /v1/firm/sso/portal-link`.
- **Staff:** `GET /v1/firm/staff`, `POST /v1/firm/staff/invitations` (with resend and revoke), `PUT /v1/firm/staff/{user_id}/role`, `POST /v1/firm/staff/{user_id}/revoke`.
- **Checklist:** `GET /v1/firm/onboarding`, `POST /v1/firm/onboarding/dismiss`.
- **Templates:** template engagement types on the methodology routes.

## 9. Authorisation and tenancy
Existing matrix actions: `firm.manage_users`, `firm.manage_settings`, `autonomy_policy.update` (all firm admin, fresh MFA).

Sign-up is the one route that creates a tenant:
- it runs before any membership exists, as the signed-in identity (`IDENTITY` marker);
- it inserts through a reviewed definer function: firm, membership, defaults and audit in one transaction;
- it's rate-limited.

## 10. AI behaviour
None new. The autonomy policy constrains future agent behaviour (ADR-061); today it gates the platform's automatic actions (Q4).

## 11. Integrations
- **Identity vendor:** WorkOS organisations, SSO connections and the admin portal (ADR-029). A local fake stands in, so the flow works before TASK-014. The real vendor needs a WorkOS account and keys (Q2).
- **Email:** invitations are delivered through the existing transport (a local mailbox now, SES with TASK-014).

## 12. Edge cases and failure modes
- **A person signs up but their email domain already belongs to a firm with SSO:** refused, with "Your firm already uses Abacus: ask your administrator for an invitation."
- **SSO is connected wrongly:** the admin can disconnect it. Until the connection is verified (one successful SSO sign-in by the admin), enforcement doesn't start, so nobody is locked out.
- **The last firm administrator tries to leave or demote themselves:** refused.
- **An invitation is accepted by a different email than it was sent to:** refused.

## 13. Security and privacy
- **Sign-up is the main abuse surface:** verified email, rate limits and pilot gating (Q1).
- **SSO enforcement** starts only after verification.
- **Fresh MFA** is required for SSO, people, autonomy and walls (ADR-030).
- **No identity-provider secrets** are stored by Abacus; the vendor holds them.

## 14. Audit trail and evidence integrity
- `firm.created`
- `firm.settings_changed`
- `firm.sso_connected` and `firm.sso_disconnected`
- `staff_invitation.*`
- `membership.role_changed` and `membership.revoked`
- `autonomy_policy.updated`
- `onboarding.dismissed`

## 15. Observability
Time from sign-up to first engagement (the Act 0 promise), and the number of checklist steps done per firm.

## 16. Performance and scale
Small. Sign-up is rate-limited per identity and per IP.

## 17. UX
The SPEC-016 shell:
- the checklist is the first page after sign-up and a card on the engagements page until it's done;
- the Firm admin section gains People, Single sign-on and Autonomy tabs;
- sign-up is one short page.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 | integration | Sign-up creates firm, admin and defaults atomically; gating and refusals |
| AC-2 | integration | Domain enforcement after verification only; client users unaffected |
| AC-3, AC-4 | integration | Invitations, roles, revocation on the next request, last admin protected |
| AC-5 | unit and integration | Autonomy stored, audited; the gate on automatic actions |
| AC-6 | integration | Templates filtered by engagement type |
| AC-7, AC-8 | component (vitest) | Checklist states and links; every new screen's states |

## 19. Rollout
- Migrations in identity, organisations and engagements.
- Sign-up sits behind the gating in Q1.
- SSO uses the fake provider until TASK-014 brings WorkOS keys.

## 20. Open questions
- [ ] **Q1: who can sign up.** *Recommendation:* during the pilot phases, a sign-up code you issue (single-use, through tooling), so only design partners can create firms. Fully open sign-up comes later, behind a flag. *Alternative:* open now, with email verification and rate limits only.
- [ ] **Q2: SSO before WorkOS exists.** *Recommendation:* build the whole flow against the local fake provider now. Domains, the portal link, verification, enforcement and the status screen all work locally. The real WorkOS organisation and portal plug in with TASK-014's keys. SSO stays optional per firm, as a "skip for now" step on the checklist, because small firms often have none (ADR-030 then requires password or passkey with MFA, through the vendor).
- [ ] **Q3: autonomy levels shown to firms.** *Recommendation:* all four ADR-061 levels are shown. Levels 0 and 1 are selectable now. Levels 2 and 3 show "coming with the engagement agent" (increment 8) and can't be chosen yet.
- [ ] **Q4: what the level controls today.** *Recommendation:* at Level 0 (Advise), the platform takes no automatic actions: no automatic retrieval, and no automatic screening (screening becomes a "Screen now" button). At Level 1 (Routine), today's behaviour. The `retrieval.auto` flag stays as an operator kill switch on top.
- [ ] **Q5: engagement types.** *Recommendation:* `audit`, `review`, `compilation` and `agreed_upon_procedures` (the US engagement types under AICPA standards), and templates tagged by type. Everything already built treats them alike. Type-specific behaviour comes later.
- [ ] **Q6: the agent column in your diagram.** Today "validate every row" and "areas mapped to accounts" are deterministic code (the firm's own rules), not a model. *Recommendation:* keep them as code (ADR-050: code computes) and label them "Abacus checks" in the UI. A model suggesting rules for unmapped accounts would be a later spec with its evaluation suite.
- [ ] **Q7: protected paths.** *Recommendation:* an approval file covering:
  - `identity/**` (sign-up, staff invitations, roles, SSO enforcement);
  - `organisations/**` if protected;
  - `api/app.py` (new routers);
  - `schema_check.py` and `banned_patterns.py`;
  - `backend/tests/unit/**`;
  - the permission matrix (only if a new action is needed).

## 21. Future / explicitly deferred
- SCIM provisioning; billing and plans.
- Per-engagement autonomy; Levels 2 and 3 (increment 8).
- Model-suggested account mapping rules.
