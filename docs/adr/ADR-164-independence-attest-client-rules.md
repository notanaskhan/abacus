---
id: ADR-164
title: Independence and attest-client rules - a derived attest flag, G2 on assignment, sign-off and client-facing actions, an SKE designee and NAS evaluation for attest clients, no GL posting and no policy principal
status: accepted
date: 2026-10-23
deciders: notanaskhan, ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-026 made ethical walls absolute and deferred "independence-conflict rules between engagement types" to the CAS product. That product is now in scope. One firm may audit a client and also close its books, prepare its returns or advise it, and the AICPA independence rules (ET 1.295, nonattest services) apply only where the firm is the client's attest provider. The repository does not express this yet:

- SPEC-025 and TASK-045 put the independence check in `authorise` layer 3b: an action marked `independence: required` counts a staff engagement role only once that person has confirmed independence for the engagement. The check guards content reads and writes on every engagement, attest or not, through the `register_independence` slot that `engagements.api` fills (`identity/authz/__init__.py`).
- DEC-39 (b) decided the design's semantic: an unconfirmed member may *view*, but cannot be assigned work, sign off or act client-facing; a firm setting may make G2 stricter, never looser.
- DEC-69 (b) decided the attest-client rules as proposal P-13: the firm never posts to an attest client's GL, no policy principal acts for one, an SKE designee is required, G2 applies on sign-offs, and readiness work for an attest client needs a NAS evaluation.
- DEC-128 decided how the attest flag is derived, and F-03-T25 built it (migration 0082, `organisations.is_attest_client`, the `attest_client` matrix condition read through engagements).
- DEC-63 made the SKE designee and the approver of record `engagement_contacts` designations; DEC-64 (b) moved NAS evaluation into the product as a decision reserved to the engagement partner; DEC-91 added an annual firm-wide confirmation to the per-engagement one.

This ADR records P-13. The plan's chapters call it "ADR-142"; that number was minted for the AWS production topology (P-55), so P-13 takes ADR-164 (`docs/adr/backlog.md`). P-07-T24 implements the authorisation change and P-07-T41 the independence records; both are bound by this ADR.

## Decision
1. **The attest flag is derived, never set (DEC-128 kept).** A client is an attest client while it has an engagement of the attest gate family (`engagements/gate_policy.py`: `fs_audit`, `ebp_audit`, `review`, `agreed_upon_procedures`, `soc1`, `soc2`, `readiness`, `internal_audit`) in status `accepted`, `contracted`, `active`, `on_hold` or `delivered`. `clients.is_attest_client` is recomputed by the SECURITY DEFINER trigger on `engagements` in the same transaction as any insert or change of status, type or client; the app role cannot write it. Prospect, declined and archived engagements do not count. The flag belongs to the client, so it applies across the client's engagements: a CAS close or a tax return for an attest client is an engagement of an attest client. Code reads it only through `organisations.api.attest_client_of` or the matrix condition `attest_client: only | deny`; nothing caches it beyond a request.
2. **G2 v2: view yes; assignment, sign-off and client-facing actions no (DEC-39).** For an engagement whose client is an attest client, a team member who has not confirmed independence for that engagement:
   - may read the engagement and its content (the `independence: required` marker no longer guards content reads);
   - may not be **assigned**: `work_item.assign` (and `todo.assign` when P-05 adds it) targeting that person answers `409 gate_unmet` with gate `G2` and the person as an identifier fact; ENG-05's "Blocked assignment" renders it;
   - may not **sign off**: P-04's sign-off service refuses through `engagements.api.independence_cleared` with `409 independence_pending` (ADR-160 R-SO-5);
   - may not **act client-facing**: `message.send`, `request_item.send` and `client_access.grant` keep `independence: required` for the acting member.
   For an engagement whose client is not an attest client, no G2 condition applies (`attest_client: only`). Per-person confirmation is still requested on assignment (DEC-91) and recorded, but it gates nothing there.
3. **Stricter only.** The registered firm setting `g2_blocks_view` (bool, default false) restores TASK-045's read gate for attest-client engagements: pending members also lose content reads. No setting, gate policy or role may loosen item 2. Until P-07-T24 merges, TASK-045's behaviour stands; it is stricter, so no control is weakened before its replacement lands.
4. **One answer, one slot.** "Is this person cleared on this engagement" is answered in one place: the engagements module's confirmation lookup, registered with identity through the existing `register_independence(column, lookup)` slot (for `authorise` and `visible()`) and exported as `engagements.api.independence_cleared(tenant, engagement_id, user_id)` for P-04 and assignment. Cleared means a confirmation by that person for that engagement that no later decline supersedes; the annual firm-wide confirmation (DEC-91, collected in ADM-02 by G-01, DF-07) joins the predicate when G-01 delivers it. Unregistered or unknown answers *not cleared* (fail closed). No module re-derives it.
5. **The engagement's G2 gate is a human conclusion.** The G2 gate provider reports G2 met when an insert-only `independence_conclusions` row exists with option `independent` or `independent_with_safeguards`. The conclusion is reserved to the engagement partner with fresh MFA, and refused with `409 independence_preconditions_unmet` (blockers as identifier facts) unless every team member has confirmed, conflicts are cleared and, for an attest client, items 6 and 7 hold. `not_independent` keeps G2 unmet. A logged breach keeps the banner until its evaluation, TCWG communication and remediation are recorded as insert-only events.
6. **SKE designee required for attest clients.** An attest client's engagement needs an SKE designee: a named client contact designated through `engagement_contacts` (DEC-63) and mirrored onto grants. Without one, NAS evaluation and the G2 conclusion are refused. A non-attest client needs none and the UI says so ("Non-attest client: no SKE designation required").
7. **NAS evaluation for attest clients.** Every nonattest service the firm provides to an attest client (a CAS close, tax preparation, advisory, readiness work, as DEC-69 names) is a row on that client's attest engagement's NAS matrix, evaluated under ET 1.295 with the SKE designee recorded, insert-only with events. A partner or manager prepares a row (`nas.evaluate`, P-07 §4.3); the evaluation decision on each row is reserved to the engagement partner (DEC-64). The independence conclusion is refused while a listed service lacks a decided evaluation. Readiness counts toward the attest flag by DEC-128's list; when it is the client's only attest-family engagement, there is no other attest engagement to evaluate it against, so no NAS row is required for it.
8. **No GL posting for attest clients.** P-16's GL write capability (W1) declares `attest_client: deny`: the firm never posts to an attest client's ledger; the client approves and records, and "Export instead" stays. Because the flag is evaluated at request time, a client that becomes attest stops accepting posts at once, including approved batches not yet sent.
9. **No policy principal for attest clients.** The dormant policy actor (P-08, ADR-161 item 7) may never be enabled for an attest client's engagements; its grants declare `attest_client: deny`, so enabling it later cannot reach them.
10. **Humans only.** `independence.confirm` (self only, `not_self` otherwise), `independence.conclude`, `nas.evaluate` and the breach events deny `agent` and `system` at the matrix, `require_live_human` and the human-only CHECK layers (INV-1). An agent run is bound by its initiator's G2, as today.

Solo-edition reading: "accepted by both founders" is recorded as acceptance with both handles in `deciders` (`docs/plan/AMENDMENT-solo.md`); there was no meeting.

## Options considered
### Option A: attest-only G2 on assignment, sign-off and client-facing actions, with a stricter firm setting - chosen
- Pros: matches DEC-39 and the design (CLI-08, ENG-05: Kira Ross opens the engagement but cannot be assigned); keeps tax and CAS portals free of an audit-only gate (ADR-136 gate policy); one lookup for every consumer; firms that want TASK-045's stricter rule keep it.
- Cons: an unconfirmed member of an attest engagement can read content by default; the change touches the protected authorisation path.

### Option B: keep TASK-045 (G2 guards every content read on every engagement)
- Pros: strictest; already built.
- Cons: blocks tax and CAS work on an audit-only rule; contradicts DEC-39 and the designed screens; offers no sign-off or assignment refusal with a reason.
- Why rejected: DEC-39 (b) chose the design.

### Option C: a stored attest flag edited by a firm admin
- Pros: simple to explain.
- Cons: drifts from the engagements that make a client attest; an admin could turn off the rules that protect independence.
- Why rejected: DEC-128 derives it; a derived flag cannot be loosened by hand.

### Option D: G2 for every engagement type, attest or not
- Pros: one rule.
- Cons: nonattest services carry no independence requirement; applies audit friction to tax season.
- Why rejected: ET 1.295 and DEC-69 scope the rules to attest clients.

## Consequences
**Positive**
- Independence is enforced where the profession requires it, and the reason is visible at the point of refusal (assignment dialog, sign-off, gate rows).
- Tax and CAS work for non-attest clients is never blocked by an audit gate.
- The firm cannot post to an attest client's books or let a policy principal act there, whatever its settings.

**Negative / costs accepted**
- By default a pending member of an attest engagement can read its content before confirming; firms that object set `g2_blocks_view`.
- Every consumer (sign-off, assignment, client-facing sends, GL writes, the policy actor) must call the shared check; a missed call is a gap, caught by the generated matrix tests and the AC suite.

**Follow-up work created**
- **Authorisation (P-07-T24, red):** re-scope `independence: required` per item 2 with `attest_client: only`; `firm_setting(g2_blocks_view)`; `engagements.api.independence_cleared`; `work_item.assign` refusal; matrix edits in `engagements.yaml` and the client-facing rows.
- **Records (P-07-T41):** `independence_conclusions`, `nas_evaluations` and events, breaches, the SKE designee precondition, `independence_preconditions_unmet`, the G2 gate provider.
- **Tests:** P-07's ADR-078 AC suite for T24 and T41 (assignment, sign-off and client-facing refusals; non-attest not gated; stricter setting; humans only).
- **Downstream:** P-04 sign-off calls `independence_cleared`; C-01 / P-16 declares `attest_client: deny` on GL writes; Q-03 / P-08 declares it on policy-principal grants; G-01 adds the annual confirmation to the predicate.
- **Docs:** identity and engagements READMEs (G2 v2) in P-07-T64; P-07-T02's superseding SPEC cites this ADR.

## Enforcement
- [ ] Test: on an attest-client engagement, a pending member reads content (200), is refused `work_item.assign` with `409 gate_unmet` G2 and sign-off with `409 independence_pending`, and is refused `message.send`, `request_item.send` and `client_access.grant`; with `g2_blocks_view` on, content reads are refused too.
- [ ] Test: on a non-attest engagement (CAS close, tax), none of the above is gated by independence.
- [ ] Test: the attest flag follows the engagement trigger (F-03-T25's trigger test holds its lists to `gate_policy` and the lifecycle; RK-32).
- [ ] Test: the conclusion is refused without every confirmation, cleared conflicts, the SKE designee and every NAS evaluation (attest), and is human-only with fresh MFA.
- [ ] Test: GL write and policy-principal actions on an attest client are denied by the matrix (`attest_client: deny`) when those epics land.
- [ ] Hook or protected path: `identity/authz/*` and the permission matrix are protected; the matrix generator rejects a firm setting that loosens a rule.
- [ ] Reviewer agent checklist item: no module computes independence or the attest flag itself; every assignment, sign-off and client-facing send goes through the shared check.

## Guidance for agents
Ask the one check; never re-derive it. Read the attest flag through the matrix condition or `organisations.api.attest_client_of`, and independence through `engagements.api.independence_cleared` or `authorise`.

**Do**
```python
if not await engagements_api.independence_cleared(ctx.tenant, engagement_id, assignee_id):
    raise GateUnmet("G2", facts={"user_id": str(assignee_id)})
```

**Don't**
```python
if client.kind == "plan_sponsor":   # guessing "attest" from the client's kind
    ...
```

## Revisit when
The AICPA changes ET 1.295 or the firm serves issuers (SEC/PCAOB rules would add restrictions this ADR does not model); a firm needs a G2 rule stricter than `g2_blocks_view`; or the attest gate family in `gate_policy.py` changes (DEC-128's list moves with it).

## Related
- P-ID: P-13 (DEC-69 b, DEC-39 b), drafted by P-07-T66. Plan alias "ADR-142" maps to ADR-164 (`docs/adr/backlog.md`).
- Follows up ADR-026 (its deferred independence rules). Builds on ADR-136 (gate policy, G2 as a registered gate), ADR-147 (the `attest_client` condition), ADR-160 (R-SO-5 sign-off refusal), ADR-161 (dormant policy actor), ADR-150 (write capabilities); consistent with DEC-128, DEC-63, DEC-64, DEC-91.
- Docs: `docs/plan/09-decisions-adrs.md` P-13, DEC-39, DEC-69; `docs/plan/epics/P-07.md` §3.5, §4.4, §4.9, R-5; SPEC-025 AC-5 and AC-7 (TASK-045), superseded in part by P-07-T02's SPEC.
