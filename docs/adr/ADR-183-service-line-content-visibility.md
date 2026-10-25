---
id: ADR-183
title: Service-line content visibility - a firm may open a line's content, read-only, to the line's members; never Audit, attest clients, walled or offshore members, or admins
status: proposed
date: 2026-10-26
deciders: ayushkbhatia, notanaskhan
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.
> - **This ADR is proposed.** It is G-01 OQ-1 ("Service-line content visibility", the Jan 29, 2027 decision), decided in session as DEC-380 under AMENDMENT-solo item 7 with OQ-1's recommended option. It extends ADR-024; it does not relax it for admins. Its switch is `authz.SERVICE_LINE_REACH`: set it to False for G-01 AC10.4's fallback (every line "Engagement team only").

## Context
ADM-03's revision R2 lets a firm set, per service line, who reads a line's content: the engagement team only, or the whole line. ADR-024 grants content to an engagement's team and, in their scope, to practice leaders and quality partners; firm admins see metadata only and join to see content. A tax or client-accounting practice often works as one pool: a preparer covers a colleague's return without being added to every engagement. G-01 §3.10 (AC10.1 to AC10.4) and OQ-1 describe the setting and recommend a narrow form of it; no register row decided it.

## Decision
A firm may set a service line's "Content visible to" to "Service line". The line's members then read that line's engagements as a team member with the `staff` role reads them, for plain reads only, under these rules, all enforced in `authorise` and `visible()` (one derived role, `service_line_reader`):
1. **Read-only.** Only actions that are reads with no fresh-MFA, reason, notify or condition rule. Never a write, a sign-off, a decision or client contact.
2. **Never Audit, never attest.** Audit is locked to "Engagement team only" (422 `audit_locked`, and a database CHECK). An engagement whose client is an attest client, or whose attest flag is unknown, is never reached, so G2 (ADR-164) never needs to apply to the reach.
3. **Walls first.** A wall denies as for every role (ADR-026).
4. **Not offshore.** An offshore member is never reached through a line (DEC-52; the consent provider is not registered, and a line read is not an assignment).
5. **Admins stay metadata-only (ADR-024).** A firm admin or security admin, or a member on level `admin`, is never a reader.
6. **A member of the line.** The person's `service_lines` include the engagement's line and they hold no engagement role there (a team role decides as before).
7. **Off by default, audited, immediate.** A firm without a policy row reads every line as "Engagement team only". A change is fresh-MFA, a live person's, audited, and tells every member holding the line their access changed; it applies on their next request.

## Options considered
### Option A: read-only line reach with the exclusions above - chosen (OQ-1's recommendation)
- Pros: matches how tax and CAS pools work; narrow; admins and attest work untouched; one switch.
- Cons: widens who reads non-attest content in firms that opt in; one more path to test.

### Option B: every line "Engagement team only" (AC10.4 fallback)
- Pros: no change to ADR-024's reach.
- Cons: the R2 design cannot be used; firms add whole pools to every engagement instead, which grants writes as well.
- Why rejected: kept as the switch, not chosen as the default answer to OQ-1.

### Option C: line reach including writes or attest engagements
- Pros: fewer joins for pools.
- Cons: breaks independence (G2) and the sign-off model.
- Why rejected: out of scope of ADR-024 and ADR-164.

## Consequences
**Positive**
- Firms can run pooled tax and CAS work without broad team memberships.
- Audit and attest work keep team-only content, enforced in the database as well.

**Negative / costs accepted**
- `visible()` carries one more subquery for people on a staff membership.
- A firm that opens a line widens non-attest content to its members; every such change is audited.

**Follow-up work created**
- "By request (partner approves)" stays stored and behaves as hand-offs only until a flow is designed (G-01 OQ-2).
- The service-line layer is a named pen-test retest item (G-01 R-2).

## Enforcement
- `identity/authz`: `service_line_reader`, `_line_reader` (authorise) and `_line_reach` (visible), sharing `_may_read_lines`; `SERVICE_LINE_REACH`.
- Migration 0167: `service_line_policies_audit_locked` CHECK.
- Tests: `backend/tests/integration/test_service_lines.py` and G-01-T15's independent suite (reach and narrowing, no write, Audit locked, attest, walls, offshore, admins, cross-tenant, list agrees with `authorise`).
