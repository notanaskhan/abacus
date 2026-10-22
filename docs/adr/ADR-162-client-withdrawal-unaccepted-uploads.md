---
id: ADR-162
title: A client may withdraw an upload the firm has not accepted - void and hide at once, crypto-erase by detached key after 30 days unless held
status: accepted
date: 2026-10-22
deciders: notanaskhan, ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Clients upload the wrong file: last year's statement, a spouse's pay stub, a document with an unrelated person's data. The portal design lets them take it back (POR-03, POR-04). The platform's rules say nothing inside an engagement is deleted (ADR-004, ADR-034), and evidence objects are content-addressed, deduplicated and kept under S3 Object Lock in GOVERNANCE mode with retention extended on reuse (ADR-016, `evidence/storage.py`). Each object today carries its own data key wrapped *inside* the object (envelope "ABE1", ADR-104), so there is no key to destroy per upload, and deleting a locked object early needs the break-glass retention override (chapter 06 C-09), which is wrong for a routine job.

DEC-58 (b) decided the behaviour: an unaccepted upload may be withdrawn; the version is voided and hidden, then crypto-erased after 30 days unless held; accepted evidence can never be withdrawn. This ADR records that decision as proposal P-31 and picks the erase mechanism left open as OQ-5 in epic P-06 (section 4.2). The plan's chapters call this ADR "ADR-137"; that number was minted for the module map, so P-31 takes ADR-162 (`docs/adr/backlog.md`).

## Decision
1. **One enumerated exception to ADR-004 and ADR-034.** A client may withdraw an evidence version that a client principal uploaded and that the firm has **never** accepted. Nothing else is withdrawable or erasable outside retention-driven destruction (P-14). Every audit event about a withdrawal is kept.
2. **Accepted means ever accepted.** Acceptance (an `accept` review decision through the REVIEW-001 path) stamps the version's key as retained, and retention is one-way. A version with an accept decision, including one later undone, answers `409 evidence_accepted`, and the portal shows no withdraw control. A returned (rejected) version is withdrawable. Withdraw and accept lock the version row, so whichever commits first wins and the other answers 409.
3. **Who may withdraw.** `evidence.withdraw` (new matrix action): `client_admin` with `client_visible_only` (an admin may withdraw contributors' unaccepted uploads in their scope, audited; OQ-5 answered yes) and `client_contributor` with `assigned_only` (own uploads only, else `403 not_your_upload`). Every firm role, `agent`, `system` and `support`: deny. The route is `POST /v1/engagements/{eid}/evidence-versions/{vid}/withdraw` with an `Idempotency-Key` (ADR-139), behind the `evidence.withdrawal` flag.
4. **Withdraw voids and hides at once.** In one unit of work: an insert-only `evidence_withdrawals` row (`version_id`, `withdrawn_by_user_id`, `withdrawn_at`, `erase_after = withdrawn_at + 30 days` on `kernel.clock`), the outbox event `evidence_version.withdrawn` and the audit event. From that commit the version is excluded from every firm read (lists, board summary, previews, search projections, inbox), from agents (review material, matcher, screening; in-flight runs record nothing for it) and from exports. If it was the request item's only fulfilment, the request returns from `uploaded` to `requested`. The firm's Activity shows that the client withdrew an upload, without the file name.
5. **Erase mechanism: detached-key crypto-erase (chosen over rolling retention).** Client-channel uploads are stored in **detached-key mode**: object key `tenants/<tenant>/v/<version_id>`, never shared by deduplication; envelope "ABE2", whose data key is wrapped by the firm's tenant key (ADR-035, ADR-104, ADR-156) and stored in `evidence_object_keys(version_id, key_id, wrapped_key, created_at, retained_at, destroyed_at)`, not in the object. `evidence_versions` gains `storage_mode in {content_addressed, detached_key}` (default `content_addressed`). Acceptance stamps `retained_at`, after which a trigger forbids clearing the key. Erasing sets `wrapped_key` to NULL and stamps `destroyed_at` through one SECURITY DEFINER function callable only by the purge activity's role. The ciphertext is unreadable at once and ages out under its existing GOVERNANCE retention; the erase record states that unreadable ciphertext persists until that date, as the offboarding certificate does (RB-13). The tenant key is never touched. Firm uploads, connector retrievals and generated files stay content-addressed. Duplicate detection keeps using the fingerprint column (DEC-58 g).
6. **Derived records go with the key.** Previews of a detached-key version are written under that version's data key, so the same erase covers them. Extraction results and search projections are derived and rebuildable (ADR-110) and are deleted by the purge in the same run. The `evidence_versions` and `evidence_withdrawals` rows remain as identifier-only tombstones.
7. **Purge after 30 days, never while held, fail closed.** `EvidenceWithdrawalPurge` (Temporal, ID `withdrawal:<tenant>:<version>`, reuse policy reject) starts from the withdraw unit of work's outbox event, sleeps on a durable timer to `erase_after`, then: checks for a legal hold on the engagement or client (ADR-033, P-14 registration); with no hold, destroys the key, deletes derived records and records `evidence_withdrawal.erased`; with a hold, records `evidence_withdrawal.erase_blocked` and retries each business day. If no hold check is registered, the purge fails closed and erases nothing; withdrawal still hides at once.
8. **Scope of the mechanism.** Only detached-key versions can be withdrawn. Client uploads stored before detached-key mode exist only in synthetic tenants (no real data before the M7 gate) and are not withdrawable; no backfill.

Solo-edition reading: "accepted by both founders" is recorded as acceptance with both handles in `deciders` (`docs/plan/AMENDMENT-solo.md`); there was no meeting.

## Options considered
### Option A: detached-key crypto-erase for client-channel uploads - chosen
- Pros: erases on day 30 exactly, under the normal worker role; no break-glass override; leaves Object Lock and content-addressing untouched for everything else; the same idea as offboarding's crypto-shred, at version scale.
- Cons: a second storage mode and envelope version; a key table on the read path for client uploads; deduplication does not apply to client uploads.

### Option B: short rolling retention, extended on acceptance, deletion on lapse
- Pros: no new envelope.
- Cons: the erase happens when retention lapses, later than 30 days; every unaccepted upload needs retention bookkeeping; deletion of objects still needs a lifecycle path.
- Why rejected: misses DEC-58's 30-day promise (epic P-06 section 4.2 recommends against it).

### Option C: early delete under the retention override
- Pros: the object is gone.
- Cons: uses break-glass dual control (chapter 06 C-09) for a routine daily job.
- Why rejected: break-glass must stay exceptional (ADR-028).

### Option D: hide only, never erase
- Why rejected: DEC-58 promises erasure, and the portal copy says so (DF-15).

## Consequences
**Positive**
- A client's mistake can be undone without weakening immutability for anything the firm relied on.
- Erasure is provable: a key row with `destroyed_at` and an erase record.

**Negative / costs accepted**
- Client uploads are not deduplicated in storage.
- Unreadable ciphertext remains in the bucket until its retention lapses.
- Every firm read path and agent material builder must filter withdrawn versions.

**Follow-up work created**
- **Storage and schema:** envelope v2 with detached key, `evidence_object_keys`, `storage_mode`, migration `evidence_withdrawals`, key retained on acceptance (P-06-T18).
- **Route and workflow:** withdraw route, hide-everywhere filters, status rollback, `EvidenceWithdrawalPurge` with a replay history and a 30-day time-skipping test, the `evidence.withdrawal` flag (P-06-T19).
- **Tests:** accepted never withdrawable, hidden from agents and exports, erase only after 30 days and never while held, fail closed without a hold check (P-06-T23).
- **Glossary and copy:** `evidence_object_key`, UI "Withdraw" (P-06-T04); portal copy per DF-15 (R-01).
- **Contract:** C5 lists withdraw as a client-only action with its audit events (P-06-T01).

## Enforcement
- [ ] Test: withdraw on an ever-accepted version answers `409 evidence_accepted`; a contributor withdrawing another's upload answers `403 not_your_upload`; firm, agent and system principals are denied (generated matrix tests).
- [ ] Test: after withdrawal no firm read, agent material builder, search projection or export returns the version.
- [ ] Test: the purge erases nothing before `erase_after`, nothing while held, nothing when no hold check is registered; after erase the version cannot be opened.
- [ ] Database: trigger forbids clearing a retained key; only the purge role can call the erase function; `evidence_withdrawals` is insert-only apart from its stamp columns.
- [ ] Reviewer agent checklist item: no other delete path for evidence; no read path that skips the withdrawn filter.

## Guidance for agents
Treat a withdrawn version as if it never arrived, except in the audit trail. Never erase by deleting an object; erase by destroying the version's detached key through the purge.

**Do**
```
versions = await repository.visible_versions(ctx, item_id)   # excludes withdrawn versions
```

**Don't**
```
s3.delete_object(Bucket=b, Key=key, BypassGovernanceRetention=True)   # break-glass, not a purge
```

## Revisit when
A client needs to withdraw an accepted file (that would be a new ADR, likely through P-14 destruction); real firms report that 30 days is wrong; or storage moves away from Object Lock GOVERNANCE.

## Related
- P-ID: P-31 (DEC-58 b, DF-15, OQ-5), drafted by P-06-T28. Plan alias "ADR-137" maps to ADR-162 (`docs/adr/backlog.md`).
- Enumerated exception to: ADR-004 and ADR-034. Builds on ADR-016, ADR-033, ADR-035, ADR-104, ADR-156 (tenant keys), ADR-110 (derived records), ADR-146 (client roles and scopes), ADR-158 (client-scoped evidence); relates to ADR-028 (break-glass stays exceptional).
- Docs: `docs/plan/09-decisions-adrs.md` P-31, DEC-58, DF-15; `docs/plan/epics/P-06.md` sections 3.7 and 4.2, OQ-5; `docs/plan/06-platform-ops-security.md` RB-13.
