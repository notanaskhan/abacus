---
id: ADR-187
title: Policy principal (dormant) - the `policy` actor kind is designed, stored off and locked, and reachable only in fixture mode
status: accepted
date: 2026-10-26
deciders: ayushkbhatia   # solo edition (docs/plan/AMENDMENT-solo.md item 7): decided with the plan's proposed option, DEC-53 (b)
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
This is proposal **P-08** (chapter 09 §9.4.2; agent ADR AG-10), the record of **DEC-53 (b)**. The plan's chapters call it "ADR-149"; that number was a plan alias, and ADR-149 on `main` is P-26 (e-signature). The number here comes from `docs/adr/backlog.md`, drafted with G-02-T01 (TASK-1289).

The blueprint adds threshold auto-acceptance: a firm-approved policy ("BH AJE thresholds v2") accepts within-threshold entries without a person. ADR-005 says only a named human decides. ADR-161 item 7 already added `policy` to the actor-kind vocabulary and locked it off (`fvv_policy_dormant`, the human-only CHECKs, the matrix), and migration 0096 lets `audit_events.actor_kind = 'policy'` exist only with a `policy_ref`. ADR-164 item 9 forbids a policy principal on attest clients. What is missing is the decision that says how the dormant principal appears in the product and when it may be enabled. ADM-04 c and f and ADM-07 d design the enabled state.

## Decision
1. **Dormant, not built.** Season 1 ships named-human batch approval ("Entries approved by Raj Malhotra under BH AJE thresholds v2"). No context may act as `policy`; every decision table's human-only CHECK, the human-only audit register and the matrix keep refusing it. Enablement is **no earlier than Q2 2027**, never before GA (chapter 01 §1.7.2), and needs a superseding ADR, a migration and both a partner and `security_admin` to switch it on for a firm.
2. **Stored off and locked.** The AI policy (ADR-186) carries `policy_principal.on = false` and `gates[].policy_acceptance_on = false`; both are locked cells, and a draft that turns either on answers **422 `policy_loosening_refused`**. ADM-04 fieldset B and gate rows 1 and 5 read "Off" with a lock and the policy name.
3. **Fixture-only rendering.** ADM-04 c ("Allow policy acceptance?") and f ("On · non-attest only") and ADM-07 d (the `Policy: ‹name vN›` grammar and its reversal row) render **only in fixture mode**. No staging or production route or control reaches them. In production ADM-07 shows the note "Policy principal: 0 events — policy acceptance is off (AI policy vN)".
4. **The grammar is fixed now.** When enabled, a policy event reads "Policy: ‹policy name vN›" with the Scale glyph, its `policy_ref` names the policy version, it is always reversible by a person, and it is never attributed to the agent or to "Accrued Agent".
5. **Never for:** attest clients (ADR-164 item 9), L2 to L5 sign-offs, release, return approval, sends, GL posts or exports. The gate catalogue marks policy acceptance possible only on rows 1 and 5 (within-threshold AJE and the equivalent CAS row).

## Options considered
### Option A: design now, enable later (DEC-53 b) - chosen
- Pros: the schema and screens need no change later; nothing reaches a real firm before counsel, a pen test and real usage evidence; keeps ADR-005 intact today.
- Cons: fixture-only states to maintain; a locked toggle on ADM-04 that explains why.

### Option B: build and enable now (DEC-53 a)
- Pros: matches the blueprint's demo.
- Cons: an enumerated exception to ADR-005 before any firm holds real data; peer-review exposure.
- Why rejected: the plan's real-data gate (M7) and INV-1 come first.

### Option C: drop the concept
- Pros: simplest.
- Cons: the schema would need a breaking change later; ADM-04 and ADM-07 designs lose a state.
- Why rejected: chapter 09 keeps it on the roadmap (≥ Q2 2027).

## Consequences
**Positive**
- INV-1 holds in every production path; the dormant states are designed and tested in fixture mode.

**Negative / costs accepted**
- Fixture-only scenarios (ADM-04 c, f; ADM-07 d) carry parity and copy upkeep.

**Follow-up work created**
- G-02-T13 and T25 render the fixture-only states; G-02-T22 and T23 test the locks; C-02 reads the locked row (display only).

## Enforcement
- [x] Database: `audit_events_policy_names_its_policy` (0096), `fvv_policy_dormant` and the human-only CHECKs (ADR-161) already refuse a policy actor.
- [ ] Test: AC-48 in SPEC-349 (fixture-only states; a draft turning policy acceptance on answers 422).
- [x] Test: the generated resolution-action and matrix tests deny every decision action to non-human principals.
- [ ] Reviewer agent checklist item: any production path that renders the Policy grammar is a defect.

## Guidance for agents
Do not write `actor_kind='policy'` anywhere. Render the Policy grammar only from fixtures, and keep every policy-acceptance cell Off + Lock.

**Do**
```
if scenario.fixture_only:  # ADM-07 d
    render_policy_row(event)
```

**Don't**
```
TenantContext(tenant_id, "policy", "policy:bh-aje-thresholds-v2")
```

## Revisit when
No earlier than Q2 2027, after GA, with counsel's view, pen-test evidence and a pilot firm's request; enabling it supersedes items 1 and 3.

## Related
- ADRs: ADR-005, ADR-161 (item 7), ADR-164 (item 9), ADR-186 (P-49)
- Specs: SPEC-349 (AC-48)
- Docs: `docs/plan/09-decisions-adrs.md` DEC-53, P-08; `docs/plan/epics/G-02.md` §0.1, §2.3
