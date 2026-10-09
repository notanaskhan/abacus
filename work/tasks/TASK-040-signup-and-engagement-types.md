---
id: TASK-040
title: Self-serve sign-up and engagement types
spec: SPEC-024
acceptance_criteria: [AC-1, AC-6, AC-8]
risk_zone: red
status: awaiting-plan-approval
branch: task-040-signup
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
The first of SPEC-024's three tasks:
- a firm administrator signs the firm up with a code you issue;
- engagements gain their four types, with methodology templates tagged by type.

## Scope
SPEC-024 AC-1, AC-6 and AC-8 (for these screens). The split (D1):
- **TASK-041:** people, roles and SSO (AC-2 to AC-4);
- **TASK-042:** autonomy and the onboarding checklist (AC-5, AC-7). The checklist moves to the last task, so every step it links to exists when it ships.

## Context to load
- Spec: `docs/specs/SPEC-024-act-0-the-firm-gets-ready.md`; ADR-002, ADR-029, ADR-030
- Code:
  - `identity` (`sign_in`, `current_identity`, `VerifiedIdentity`, and migration 0025's `provision_client_user` as the pattern);
  - `firms` and `memberships` (migration 0004);
  - `engagements` (create, methodology templates, apply);
  - `abacus_tools.fakes.oidc_server`;
  - `apps/web` `Layout`, `Engagements`, `Methodology`.

## Plan
- [ ] Plan approved by human

### What the code shows
- **`firms` belongs to identity and is protected.** The app role can't insert firms. Firms exist only through the seed script.
- **A brand-new identity can't sign in at all:** `sign_in` refuses an unknown user (`NoActiveTenant`), and the SPA shows an error.
- **Client acceptance already provisions users** through reviewed definer functions (`provision_client_user`, `add_client_membership`). Sign-up follows the same pattern.

### Design (for founder review)
1. **Sign-up codes (D2):**
   - a global table `signup_codes`: id, `code_hash` (SHA-256), `note`, `created_at`, `expires_at`, `used_at`, `used_tenant_id`;
   - no app grants; it's read and spent only by the definer function;
   - you issue codes with `python -m abacus_tools.signup_codes issue --note "Design partner: …" [--days 30]`, which prints the code once, and can list them;
   - single-use, 30 days by default.
2. **The definer function `firm_signup(code_hash, issuer, subject, email, display_name, firm_name)`** (migration 0032, reviewed in `schema_check`), in one transaction:
   1. check the code (exists, unused, unexpired) and spend it;
   2. refuse an identity that already holds a staff membership anywhere (one firm per sign-up, SPEC-024 §4);
   3. find or create the user;
   4. create the firm with a new tenant ID, `created_by`, and a membership as `firm_admin`;
   5. return the tenant ID, or a refusal code (`invalid_code`, `already_member`).

   Budget, autonomy and flags need no rows: absence means their safe defaults.
3. **Service and route:**
   - `POST /v1/signup` (`IDENTITY` marker: a verified token, no membership needed) with `{code, firm_name}`;
   - the identity must carry a provider-verified email (SPEC-015's `email`);
   - after the function, `firm.created` is audited in the new tenant (a unit of work in its context);
   - refusals: 409 `invalid_code`, 409 `already_member`, 422 for a missing verified email or a bad name.
4. **Signed in but no firm:**
   - `GET /v1/me` already works for a signed-in user (SELF). `sign_in` gains a path for a known-but-memberless or unknown identity: `/v1/me` returns no memberships instead of an error;
   - the SPA then shows "You're not part of a firm yet", with "Set up your firm" (to `/signup`) and "Waiting for an invitation?";
   - nothing else opens for a memberless identity.
5. **Sign-up page** (`/signup`, outside the firm workspace):
   - signs in first if needed, then asks for the firm name and the sign-up code;
   - on success it chooses the new firm and opens the workspace;
   - plain messages for each refusal.
6. **Engagement types (D3):**
   - `engagements.type` allows `audit`, `review`, `compilation` and `agreed_upon_procedures`;
   - creating an engagement asks for its type (default `audit`);
   - `methodology_templates.engagement_types` (text array, default `{audit}`) can be set when uploading a version or changed later (`methodology.manage`);
   - "Apply methodology" on an engagement offers only the templates for its type;
   - the engagements list and overview show the type.
7. **Local identities:** the fake OIDC provider gains `dev-new` ("Nina New", verified email, no firm), so sign-up can be tried locally.

**Protected paths (approval file):**
- `backend/src/abacus/modules/identity/**` (sign-up service and route, the memberless `/me`);
- `backend/src/abacus/api/app.py` (the sign-up router);
- `backend/src/abacus_tools/quality/schema_check.py` (the global table, the definer function);
- `backend/src/abacus_tools/quality/banned_patterns.py` (if needed);
- `backend/tests/unit/**`.

Checked and not needed:
- the permission matrix: sign-up uses the `IDENTITY` marker, and templates use the existing `methodology.manage`;
- `organisations`: not protected and not changed. Engagements isn't protected.

### Questions for approval
- **D1. Split SPEC-024 into TASK-040 (sign-up, engagement types), TASK-041 (people, roles, SSO) and TASK-042 (autonomy, checklist), with the checklist last so all its steps exist?** *Recommendation: yes.*
- **D2. Sign-up codes are single-use, expire after 30 days, are issued by you through a command-line tool, and are stored only as hashes?** *Recommendation: yes.*
- **D3. A template can serve several engagement types (a list); existing templates become audit templates?** *Recommendation: yes.*
- **D4. Write the approval file for the paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — SPEC-024 approved and merged (#74). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
