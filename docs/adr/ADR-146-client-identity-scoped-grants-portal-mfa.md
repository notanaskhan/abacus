---
id: ADR-146
title: Client identity - scoped grants, link principals and portal MFA
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Client access is an engagement-scoped grant with two client roles, and client MFA is optional. Accrued's portal needs access scoped to an entity, a request, a K-1 package, a governance room or a component, with several roles at once, and a one-object path for respondents and prospects who have no account. Plan decision DEC-34 settles this, with DEC-63 and DEC-67; this ADR is P-09 in the plan's ADR backlog.

## Decision
- **Scoped grants.** `client_access_grants` holds 12 roles across 9 scope kinds, optional `document_classes[]`, and a role union. Roles: `owner`, `contributor`, `plan_administrator`, `trustee`, `taxpayer`, `spouse`, `delegate`, `third_party`, `k1_recipient`, `tcwg`, `prospect`, `component_auditor`. Scope kinds: `client · client_entity · engagement · work_item · request_item · k1_package · governance_room · component · intake`.
- **Link principals.** A signed link plus an email one-time code, as one object, for POR-17 respondents and POR-18 intake. It reads or submits exactly one object and has no session beyond the page. The POR-19 QR hand-off is a 10-minute capture session.
- **MFA is required** for scopes that bear TRI, signing and approving (Safeguards Rule 314.4(c)(5)).
- **Third parties.** A third-party grant names a person; the organisation is an attribute. A component auditor is a grant role at `component` scope.

## Options considered
### Option A: scoped grants plus link principals — chosen
- Pros: fits entity, K-1, governance and component access; respondents need no account; role union avoids duplicate users.
- Cons: a new table, a data migration and a new principal type.

### Option B: engagement-scoped grants only
- Pros: no change.
- Cons: cannot express entity, request, K-1 or component access.
- Why rejected: the portal screens need scopes the engagement grant cannot carry.

## Consequences
**Positive**
- The portal shell and its scopes derive from the union of a person's grants.

**Negative / costs accepted**
- Dual-read of old engagement client roles for one release, then contract.
- Portal sign-in needs MFA enrolment for the scopes above.

**Follow-up work created**
- Code: `client_access_grants`, role union, `portal_scopes`, scope resolvers, `access.changed` events, migration of `engagement_members` client roles (epic F-03, S2; task F-03-T26); link principals and capture sessions in the portal epics.
- Specs: portal specs POR-01..23 and CLI-04 name their scope kind and MFA rule.
- Glossary: `link principal`, `grant`, `scope kind`.
- Matrix: `scope_only` condition on every portal read and write; MFA condition on TRI, signing and approving scopes (F-03-T24, S2).
- Registry: grant role and scope-kind lists; error codes for MFA required.

## Enforcement
- [x] Test: generated allow and deny tests for `scope_only` (F-03-T24).
- [x] Test: role-union portal shell for a multi-grant client (F-03-T26).
- [x] Test: a TRI, signing or approving scope refuses a session without MFA.
- [ ] Advisory only: none.

## Guidance for agents
Read a client's access from grants, never from an engagement column. Use a link principal only for a single named object. Do not add a new client role without a matrix row.

**Do**
```python
authorise(ctx, "request_item.upload", resource)   # scope_only checks the grant
```

**Don't**
```python
if user.client_role == "owner": ...   # role check outside the matrix
```

## Revisit when
A scope kind or client role is added, or counsel changes the MFA requirement.

## Related
- Plan: P-09 (section 9.4.2); DEC-34, DEC-63 and DEC-67 (all open in `docs/product/decision-log.md` at time of writing; the plan's proposed option is taken); C-08, R-29.
- Amends ADR-002: its clause "All data access comes from a `Membership` (firm staff) or an engagement-scoped client access grant" becomes a scoped client access grant, with engagement as one of nine scope kinds. The one-global-identity and one-tenant-per-request clauses stand.
- Amends ADR-030: its clause "Client users use passwordless email links with optional MFA" now requires MFA for TRI-bearing, signing and approving scopes. Firm-user, session and sensitive-action clauses stand.
- ADRs: ADR-141 (WorkOS portal sign-in, unchanged), ADR-145 (`portal_scope` kind).
