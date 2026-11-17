---
id: ADR-344
title: Client-ledger writes (W1) and GRC request sync (W5)
status: accepted
date: 2026-11-17
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

P-16 (DEC-69). The plan's alias for this ADR is "ADR-161"; that number is P-35 on `main`
(approval grants and Undo), so P-16 takes the next free number, ADR-344 (`docs/adr/backlog.md`).
Drafted and accepted with C-02-T01 (TASK-8500, DEC-5500) under AMENDMENT-solo.

## Context
CAS clients want the month's approved adjusting entries in their own QuickBooks Online, not in a
file somebody re-keys. That is the first write into a client's system (shape W1). ADR-040 makes
every connector read-only and ADR-150 (P-17) built the declared write-capability framework that
refuses W1 and W2 until an ADR opens them. Attest independence (ET 1.295, ADR-164, P-13) forbids
the firm from posting to an attest client's books. Agents never decide (ADR-005) and every
external effect runs through a single-use approval grant with a 10-second Undo (ADR-161, P-35).

## Decision
1. **One W1 capability**, `ledger_post_journal_entries` in `docs/architecture/write-capabilities.yaml`
   (adapter `quickbooks_online_poster`, owner C-02). Its only operations are
   `create_journal_entry` and `set_closing_date`. It never edits or deletes an existing
   transaction, never writes an attachment and never changes a chart of accounts. A
   recategorization approved in CLS-04 or CLS-06 posts as a reclassification journal entry.
2. **Human-approved batches only.** Every write belongs to a `posting_batches` row created by a
   named person holding `posting_batch.post` with a fresh MFA step-up (15 minutes). A single
   "Post AJE" is a batch of one. The batch carries a single-use approval grant over the payload
   hash (entries, lines, dates, closing date) with `not_before = +10 s`; Undo inside the hold
   voids it and nothing is written. The policy principal (ADR-187, P-08) never approves or posts.
3. **Five switches, all checked when the grant is consumed**: the registry entry (`enabled`),
   the firm's `firm_write_capabilities` row (security_admin, fresh MFA), the engagement's
   `posting_enabled`, the client owner's `connection_write_grants` row (granted in POR-16 with
   consent copy `por16.qbo.post_entries.v2`), and the per-firm kill switch
   `write.ledger.post_journal_entries`. Any one off fails the batch closed with its reason.
4. **Never for an attest client.** A client entity with an attest flag (ADR-164) can hold no
   write grant (trigger), every entry classifies `review_required` / `attest_client`, and a batch
   containing one is refused `attest_client_posting_refused` at the registry, the grant and the
   workflow. Attest CAS entries go to the client for approval (C18) and are recorded once the
   client's own entry is matched or evidenced (`recorded_externally`).
5. **Idempotent, verified, reversible by a new write.** The idempotency key is
   `{posting_batch_id}:{proposed_entry_id}`; before any re-write the activity re-reads by
   DocNumber and the private-note marker. Each write is read back and compared line for line; a
   mismatch is `verify_mismatch`, flips the firm's kill switch, opens a SEV2 under RB-30 and is
   corrected by a reversing entry, never a delete. Request, response and read-back bodies are
   write-once evidence (ADR-004).
6. **The closing date is set once**, after the batch's last entry posts. An entry dated on or
   before the client's current closing date is held `closing_date_locked`; the only ways out are
   "ask the client to lift the date" (a POR-20 template row, sent by a person) and "re-date"
   (withdraws the approval). Accrued never asks for or stores a closing-date password.
7. **Auto-reversals** are created at posting time as Approved rows on the next close with
   `reversal_of_id`, and post only when a person posts that close's batch, never on a timer.
8. **Export instead stays.** Without W1 for a client the primary action exports a deterministic
   JE import file and the entry reads "Recorded in ledger" once matched or evidenced.
9. **Code paths.** Only `adjustments/posting.py` may call `integrations.api.execute_write` with a
   W1 capability (POST-001); no tax-only entry enters a batch (TJE-001); `connections` keeps no
   write-shaped method (CONN-001). Writers live in the protected
   `integrations/writers/quickbooks_online.py`.
10. **Release.** The entry stays `enabled: false` until the post-pen-test protected PR (C-02-T50);
    the pen test itself is deferred (DEC-1389), so W1 ships dark. W5 (GRC request sync) is named
    by P-16 but has no owner epic yet; it stays undeclared and refused.

## Options considered
### Option A: human-approved batches through the W1 capability — chosen
- Pros: one deliberate, audited trust boundary; idempotent; reversible; attest-safe at three layers.
- Cons: five switches to explain; fresh MFA every posting session.

### Option B: export only (no write)
- Pros: no external write at all.
- Cons: re-keying, drift between Accrued and the client's books; the design's CLS-07 d/e and
  CLS-11 cannot be honest. Kept as the fallback (decision 8).

### Option C: let the agent post within policy limits
- Pros: fewer clicks.
- Cons: breaks ADR-005 and P-08's dormancy; refused.

## Consequences
- C-02-T02 adds the matrix actions, flags, error codes, protected paths and static rules;
  T04/T05 add the tables; T06 the C8 v2 and C20 v2.1 stubs.
- ADR-040 is superseded **in part**, for the W1 adapter module only.
- Rollback: the registry entry and the firm switches default off; disabling either refuses every
  in-flight batch at its next entry.
