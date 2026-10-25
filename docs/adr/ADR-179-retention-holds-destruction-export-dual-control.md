---
id: ADR-179
title: Retention per record type and service line with counsel-set legal floors as reference data, reference-counted legal holds, dual-approved destruction and dual-control firm export
status: proposed
date: 2026-10-25
deciders: ayushkbhatia, notanaskhan
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.
> - **This ADR is proposed.** It is P-14 in `docs/adr/backlog.md` (DEC-71, DEC-72). It never defaults on silence: it is red and its floors are counsel's. It is accepted only by both deciders on `origin/main`, with counsel's floor input recorded (Q-02-T05). Until then, ADR-032, ADR-033, ADR-034 and ADR-036 bind as written, and the parts of this text already built (§"What is built") stand on their own DEC rows.

## Context
ADR-032 sets retention per engagement type with two platform minimums written into the ADR (five years for private-company audits, seven for public-company audits) and a seven-year default. ADR-033 lets firm admins hold an engagement or a client. ADR-034 offboards by export and crypto-shredding under dual control. ADR-036 lets one person with fresh MFA export an engagement. Real client data (the M7 gate, Fri Apr 16, 2027) needs more than that:

- **Record types differ inside one engagement.** A tax engagement holds signed e-file authorizations, copies of returns, source documents and workpapers; each has its own legal floor and its own clock start (a due date, a filing date, a report release). Engagement type is too coarse (epic Q-02 §3.7, R-23).
- **Floors are law, and law is counsel's.** A floor written into an ADR or a migration becomes a code change every time counsel refines it, and a wrong number in a public repository reads as advice. DEC-71 says the floors are set with counsel and never default; DEC-76 (P-62) says reference data that changes is a database set published by two people.
- **Holds must be placed by the people who learn of the matter.** A tax partner receives the IRS notice, not the firm admin (conflict C-10). Overlapping matters on the same documents must not release each other.
- **Destruction is irreversible.** The FTC Safeguards Rule asks a firm to dispose of customer information it no longer needs (16 CFR 314.4(c)(6)); professional standards and statute keep it for years. Disposal must therefore be deliberate, two-person, and never touch a held record.
- **A whole-firm export is the largest data movement there is.** One person with one factor should not be able to take everything (DEC-72, conflict C-11).

## Decision

### 1. Retention is set per record type and service line
- A **record type** is a named class of record (the code list in `evidence.retention.RECORD_TYPES` for stored objects, extended by content for database records). A **service line** is `audit`, `tax`, `cas`, `advisory` or `any`; a row for the specific line wins over `any`.
- Each record type carries an **anchor**, the event its clock starts from: `upload`, `report_release`, `filing_date`, `due_or_received_later`, `relationship_end`, `client_inactive`, `message_date`, `event_date` or `period_end`.
- A firm's **policy** (`retention_policies`) names its years, its clock-start event, a **lock** flag and a **basis** (why the firm keeps the record that long; 314.4(c)(6) asks for one). A locked policy can be lengthened, never shortened, until unlocked with a reason.

### 2. Legal floors are platform reference data set with counsel
- Floors live in `retention_floors`, a global, versioned set: imported as a draft by one platform admin, published by a **different** admin (`approved_by <> imported_by`), each row naming its authority. A published set supersedes the previous one whole.
- **No floor value appears in a commit, migration, seed, fixture or ADR.** This ADR names the floors only as placeholders; counsel's values arrive through the import (Q-02-T31) and carry counsel's approval date.
- A firm policy below the published floor is refused (`below_floor`). Where a firm has no policy, the published floor applies; where neither exists, stored objects fall back to the evidence default (`evidence_retention_days`), never to a literal year count.
- A published **default policy set** (`retention_policy_defaults`, same two-person publish) gives a firm its starting policies at provisioning and by back-fill.

The floor set's rows, for counsel. Each value is a placeholder until counsel's set is published; the authority column lists what counsel is asked to confirm, not a conclusion.

| Placeholder | Record type | Service line | Anchor | Authority for counsel to confirm |
|---|---|---|---|---|
| `FLOOR-8879` | Signed e-file authorizations (8879 family) | tax | `due_or_received_later` | IRS Pub 1345 |
| `FLOOR-RETURN-COPY` | Copies of returns prepared | tax | `filing_date` | IRC §6107(b) |
| `FLOOR-TAX-SOURCE` | Tax source documents and workpapers | tax | `filing_date` | IRC §6501(a) and (e) |
| `FLOOR-8867` | Form 8867 and due-diligence records | tax | `filing_date` | Form 8867 instructions; IRC §6695(g) |
| `FLOOR-AUDIT-DOC` | Audit documentation | audit | `report_release` | AICPA AU-C 230; state board rules |
| `FLOOR-CAS` | CAS workpapers and financial statement packages | cas | `period_end` | State board rules |
| `FLOOR-CONSENT` | Engagement letters and §7216 consents | any | `relationship_end` | Treas. Reg. §301.7216; contract evidence |
| `FLOOR-PERMANENT` | Permanent file | any | `client_inactive` | Firm need (no statute named yet) |
| `FLOOR-MESSAGES` | Email and portal messages | any | `message_date` | Firm policy |
| `FLOOR-AUDIT-EVENTS` | Audit events | any | `event_date` | ADR-007; engagement retention |
| `FLOOR-ACCESS-EVENTS` | Access events | any | `event_date` | ADR-032 security-log minimum |
| `FLOOR-RUN-RECORDS` | Agent run records | any | the engagement's `report_release` or `filing_date` | ADR-169 (engagement retention) |
| `FLOOR-INCIDENTS` | Security incident records | any | `event_date` | 16 CFR 314.4(h), (j) documentation |

### 3. Object Lock follows the record class and only ever extends
- An object's retain-until is the later of the evidence default and its record class's expiry (the longer of policy and floor, from its anchor). Uploads start anchored at upload; an anchor event (a report release, a filing date) moves the expiry later through `extend_retention_for`, audited `retention.extended` as the system, run daily by `RetentionClock`.
- Modes per class are ADR-159's (P-43): evidence in GOVERNANCE with the bypass denied to every app role; seal manifests, consent and signature evidence and chain anchors in COMPLIANCE.

### 4. Legal holds are reference-counted and override everything
- **Scopes:** a client, a client and tax year, an engagement, or a work item.
- **Who:** a firm admin, the security admin, or a partner-level member, each with fresh MFA (amends ADR-033's "firm admins"). Placing and lifting are human-only: the matrix denies agent and system and the database refuses `legal_hold.placed` and `legal_hold.lifted` from an agent or policy actor.
- **Counting:** the database is the truth. Every stored version in scope is counted in `hold_objects` in the placing transaction; a version created later in a held scope is counted in its own creating transaction, before processing. S3 follows: `LegalHoldApply` sets the object legal hold per version; `LegalHoldRelease` clears it only where no other open hold covers the same stored object.
- **Override:** no retention expiry, client withdrawal purge, destruction batch or partition drop touches a held version. The one hold check (`kernel.holds`) fails closed: with no check registered, nothing is erased.

### 5. Destruction is dual-approved and built in Q-05
- Eligible records are gathered into a **destruction batch**: those past the later of policy and floor, with no hold. The batch shows its count and recalculates when a hold arrives (held items are excluded).
- Two distinct people approve: the firm admin and the security admin (the firm's Qualified Individual). Execution needs both approvals, fresh MFA and a typed confirmation; an agent never initiates, approves or executes destruction.
- Stored objects are destroyed by crypto-shredding their detached keys (ADR-162's mechanism) once Object Lock allows it; the batch ends with a **destruction certificate** naming the batch, counts, approvers and dates. Destruction runs from Q-05 (FIL-02 c to e).
- Firm offboarding (ADR-034) keeps its export, grace period and dual control; its deletion is a destruction batch over the whole firm, still refused for held records.

### 6. Firm export is under dual control (amends ADR-036 for the whole-firm case)
- **On demand:** the security admin requests and names an approver; a partner-level member or another security admin approves; the same person can never do both (service and table CHECKs). Request, approval and every download need fresh MFA. The archive is encrypted under the tenant key with a SHA-256 manifest; a download link lives 15 minutes and can be minted for 7 days from approval; each download is audited and leaves an access event; after 7 days the archive is deleted.
- **Scheduled** (DEC-72): two people (the security admin and a partner) approve the schedule once; each run notifies both. The schedule is G-02's.
- Single-engagement export (ADR-036) is unchanged: one person, fresh MFA.

### What is built
Parts of this decision shipped under their own decision rows before this ADR was drafted, so the ADR records them rather than introducing them: floors, defaults and policies with two-person publish (migration 0112, DEC-156); Object Lock per record class and COMPLIANCE records (DEC-168); legal holds (migration 0126, DEC-228, DEC-229); the firm-export contract stub (DEC-72; `docs/contracts/compliance-kernel.md`). Not built: the daily `RetentionClock`, destruction batches and certificates (Q-05), the live firm export (Q-02-T43), the nightly hold reconciliation with S3.

## Options considered
### Option A: per record type × service line, floors as two-person reference data, reference-counted holds, dual-approved destruction and export — chosen
- Pros: matches how the law is written (by record, with its own clock); floors change without a deploy and never sit in a public commit; holds survive overlapping matters; the two irreversible acts (destroy, export everything) need two people.
- Cons: more configuration per firm; a floor set must be published before the policies mean anything.

### Option B: keep ADR-032's per-engagement-type retention with floors in code
- Pros: already written; simple.
- Cons: one clock for records with different anchors; every legal refinement is a deploy; floor numbers in a public repository.
- Why rejected: wrong grain, and it puts counsel's content in commits (DEC-71, DEC-76).

### Option C: retention by firm policy only, no platform floors
- Pros: least to build.
- Cons: a firm could shorten below the law; Accrued would have no basis to refuse.
- Why rejected: ADR-032's core promise (firms cannot under-retain) would be lost.

## Consequences
**Positive**
- A firm can see, per record type, the legal minimum beside its own longer policy (FIL-02 a).
- No held record is ever erased, by any path.
- Exporting or destroying a firm's data always involves two named people.

**Negative / costs accepted**
- Counsel's floor set is on the M7 critical path (risk R8); until it is published, firms run on defaults and the evidence fallback.
- Holds and long retention keep data longer; the basis column must justify it against the disposal rule.

**Follow-up work created**
- Q-02-T31 (floor content with counsel), Q-02-T43 and T47 (live firm export), Q-05 (destruction and FIL-02), the `RetentionClock` schedule, the nightly hold reconciliation (DEC-229), G-02's export schedule.

## Enforcement
- [x] Test: `tests/integration/test_retention_policies.py` (below-floor refusal, two-person publish), `test_retention_object_lock.py`, `test_legal_holds.py`, `backfill/test_q02t36_retention_and_holds.py`.
- [x] Database: `retention_policy_guard` trigger, `approved_by <> imported_by`, the human-only guard on hold and export actions, `HoldCheckMissing` in `kernel/holds.py`.
- [x] Matrix: `legal_hold.place`/`lift`, `retention_policy.update`, `firm_export.*` carry `mfa_recent: required` and deny the agent (`docs/architecture/permission-matrix/evidence.yaml`); the fresh-MFA lint keeps them there.
- [ ] Review check: a commit adding a year count to retention code, a migration or a fixture is refused (no lint yet; reviewers check).

## Guidance for agents
Read retention through `evidence.api.retain_until_for` and holds through `kernel.holds`. Never write a year count; never erase without the hold check.

**Do**
```python
erasable = await erasable_versions(tenant, version_ids)  # raises HoldCheckMissing: erase nothing
until = await retain_until_for(tenant, "client_document", "tax", anchor_at)
```

**Don't**
```python
AUDIT_FLOOR_YEARS = 5  # a floor in code: counsel's content belongs in the published set
```

## Revisit when
- Counsel's floor set changes a record type's grain (a new record type or service line).
- A firm needs a hold scope finer than a work item.
- Public-company audits enter scope (they are excluded today; DEC-19).

## Related
- ADRs: ADR-032, ADR-033, ADR-034, ADR-036 (amended on acceptance, not edited), ADR-016, ADR-159 (P-43), ADR-162, ADR-169.
- Specs: SPEC-341 (AC-30 to AC-37, AC-40, AC-41).
- Docs: `docs/plan/epics/Q-02.md` §3.7, §3.8, §3.10, §7.3; `docs/contracts/retention.md`, `legal-holds.md`, `compliance-kernel.md`.
- Open for counsel: every `FLOOR-*` value; the basis text per record type under 314.4(c)(6); whether "Permanent file" and "Email and portal messages" need a floor at all or only a firm policy.
