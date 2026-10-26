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
6. **A member of the line.** The person's `service_lines` include the engagement's line and they hold no engagement role there: a team role decides as before, even one the read is not granted to, in `authorise` and in `visible()` alike.
7. **Off by default, audited, immediate.** A firm without a policy row reads every line as "Engagement team only". A change is fresh-MFA, a live person's, audited, and tells every member holding the line their access changed; it applies on their next request.

## Conditions for acceptance (security review, S9 wave A; DEC-383)
The reviewer asked for these before this ADR can be accepted. All but (4) are built; (4) is the deciders' call.
1. **M1 and M2 fixed.** `visible()` no longer ORs a team member with a line reader: a row on which the person holds any engagement role is never reached through the line (rule 6), so lists agree with `authorise`. The line never counts at firm level (M2), so a firm-level read (client search, knowledge, methodology, retention policies) is exactly what it was before a line opened.
2. **Per-engagement rows only.** The reach applies only to engagement-scoped resources and to rows `visible()` filters by engagement; it is never a firm-level grant. A firm's stricter-only override of `staff`'s cell for an action keeps the reach out of that action in lists as well as in `authorise`.
3. **No agent delegation.** An agent run never inherits its initiator's line: the initiator check for an agent (its action, or the agent-only reach `evidence.read`) and the agent's list filter both leave the line out.
4. **Who may open a line.** `service_line_policy.manage` is held by firm admins and security admins, as G-01 §4.3's matrix says. A security admin is metadata-only, yet could open content to other people. The reviewer recommends firm admins and partners only; the plan says otherwise, so the plan's cell stands until the deciders choose. Every change needs fresh MFA, is a live person's own (database trigger), is human-only in the audit register and is audited.
5. **Pen-test retest.** The service-line layer stays on the pen-test retest list (G-01 R-2).

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
- `identity/authz`: `service_line_reader`, `_line_reader` (authorise, engagement resources only) and `_line_reach` (visible: no team role on the row, no `staff` override), sharing `_may_read_lines`; `_delegating` for agents; `SERVICE_LINE_REACH`.
- Migration 0167: `service_line_policies_audit_locked` CHECK and the `service_line_policies_actor` trigger; 0168: `service_line_policy.updated` in the human-only register.
- Tests: `backend/tests/integration/test_service_lines.py` (including `test_m1_…`, `test_m2_…`, `test_l1_…`, `test_l2_…`) and G-01-T15's independent suite (reach and narrowing, no write, Audit locked, attest, walls, offshore, admins, people with a team role, cross-tenant, list agrees with `authorise`).
