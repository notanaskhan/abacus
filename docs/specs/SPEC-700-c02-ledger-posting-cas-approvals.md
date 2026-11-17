---
id: SPEC-700
title: C-02 Ledger posting (W1) and CAS approvals — CLS-07 Proposed entries, CLS-11 Ledger sync and the POR-16 write grant
status: approved
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-040, ADR-043, ADR-050, ADR-089, ADR-090, ADR-108, ADR-150, ADR-161, ADR-164, ADR-187, ADR-344]
related_specs: [SPEC-655, SPEC-701]
created: 2026-11-17
updated: 2026-11-17
epic: C-02
task: C-02-T01 (TASK-8500)
---

# SPEC-700 · Ledger posting (W1) and CAS approvals

> **Instructions for coding agents**
> - The design is `docs/plan/epics/C-02.md` §1 to §8; task rows are `docs/plan/epics/C-02.tasks.csv`.
>   The user stories US-1.1 to US-6.1 and F10/F11 are adopted verbatim as the spec of record; this
>   file numbers their testable cores AC-1 to AC-24, records the gate and the open-question answers.
>   CAS deliverables, the tax hand-off and information returns (F7 to F9) are SPEC-701.
> - Contracts: `docs/contracts/adjustments.md` (C8 v2) and `docs/contracts/c20-integrations.md`
>   (C20 v2.1), C-02-T06. Screen handoffs: CLS-07, CLS-11, POR-16 (revision wins over spec).
> - **Agents never approve, post, undo, withdraw, grant or enable** (INV-1, ADR-005). **Never** for
>   an attest client (ADR-164). **Code computes** thresholds, tallies and footings (ADR-050).

## 1. Summary
A CAS team approves the month's proposed adjusting entries under the firm's threshold policy, each
approval in a named person's name, then posts the approved batch once to the client's QuickBooks
Online with the closing date set, and sees QuickBooks' ids, failures and retries in a ledger-sync
console. The client owner grants and revokes the posting scope in the portal. Attest clients are
never posted to; they approve in the portal and record the entries themselves.

## 2. Gate check (main aceddcbbf, 2026-11-17; DEC-5500)

| P-ID / decision | Subject | On main | State | What C-02 does |
|---|---|---|---|---|
| P-16 (DEC-69) | Client-ledger writes (W1) | ADR-344 (this task; plan alias "ADR-161" is P-35 on main) | accepted | W1 stays `enabled: false` (decision 10); everything else builds |
| P-13 (DEC-69) | Independence and attest-client rules | ADR-164 (plan alias "ADR-142" is the AWS topology) | accepted | attest refusal at registry, grant and workflow |
| P-17 (DEC-46) | Write-capability framework | ADR-150 (v2, DEC-1280) | accepted | W1 entry, compiled `_capabilities.py`, drift test |
| P-35 (DEC-24, DEC-28) | Approval grants, Undo | ADR-161 | accepted | `not_before = +10 s` grant per batch |
| P-08 (DEC-53) | Policy principal (dormant) | ADR-187 | accepted | stays off; CLS-07f fixture-only |
| DEC-70 | First live ledger connector: QBO | decision log | decided | writer `quickbooks_online_poster` |
| DEC-1389 | Pen tests deferred | decision log | decided | the post-pen-test flip (T50) is not reachable; W1 ships dark |

The gate is met for T02–T09. Nothing in S49 enables a write.

## 3. Contract issues (the plan's Contract Monday items)
- **contract: C8 v2 posting** — CLS-07 a (tally strip 5 · $34,920.00 / 4 · $20,020.00 /
  1 · $14,900.00 / 0 of 5 / Pending), a2 (batch modal AJE-01…04, $20,020.00), b (Approved by RM
  under BH AJE thresholds v2), c (AJE-05 $14,900.00 and AJE-06 $380.00 Review required; 10 s
  Undo), c2 (dry run: "Post 6 entries ($35,300.00) to QuickBooks Online · Copperleaf Coffee
  Roasters? The closing date will be set to Aug 31, 2026."), d (Posted · QBO 48213…48218, batch
  2026-08-A), e (AJE-03 Failed post: account 'Accumulated Depreciation' is inactive · Retry),
  f (Accepted by Policy — fixture only), g (attest client: Review required · attest clients always
  held; no Post control).
- **contract: C20 v2.1 W1** — CLS-11 a (Connected; 7 Posted, 1 Proposed, Jul 31; Authorized by
  Tess Moreno; Last sync 9:02 AM · 1,214 transactions read), a2 (Sync events), b / b2 (batch
  drawer with QBO ids), c (429: Needs attention, retrying 10:07 AM), d / d2 (Needs reauth;
  Request reconnect), e (closing-date conflict: AJE dated Aug 31 cannot post); POR-16 write grant
  (will / won't list, consent copy `por16.qbo.post_entries.v2`).
- **Consumer requests filed**: R-02 (C18 kind `close_package`, SPEC-701) and T-06 (C12 v1
  `receive_tb_handoff`, T-06-T05).

## 4. Open questions — the recommended answers (epic §11.2; DEC-5500)
- **Q1** Auto-reversals are Approved rows on the next close with `reversal_of_id`; a person posts them (ADR-344 §7).
- **Q2** W1 v1 writes journal entries and the closing date only; recategorizations post as reclassification JEs; CLS-11's write-scope row reads "Journal entries · closing date" (Deviation, C-02-T10).
- **Q4** Senior and above reject on close work items; the approver, a manager or a partner withdraws (T02 matrix).
- **Q5** Posting needs a fresh MFA (`mfa_recent`, 15 minutes) every posting session.
- **Q6** Non-W1 clients reach "Recorded in ledger" / "Recorded by ‹client›" (`recorded_externally`).
- **Q11** The policy actor stays dormant (chapter 01 wins over G-02's deferral).
- **Q15** A password-protected closing date is `closing_date_locked`; ask-client or re-date only.
- **Q16** Seed: connection Mar 4, 2026; write grant Mar 9, 2026.

## 5. Scope
In: C8 v2 (approvals, posting batches, closing-date conflicts, record external), C20 v2.1 (W1
write operations, write grants, firm capability switch, ledger console), the six rollout flags,
matrix, error codes, notification kinds, gate kinds, static rules POST-001 / TJE-001 / IRIS-001.
Out: enabling the write (T50), the live QBO writer against production (needs the Intuit
production keys, F-09-T05), the pen test (DEC-1389).

## 6. Acceptance criteria
- **AC-1** Posting exists only under ADR-344; the registry entry stays `enabled: false` and a hand edit of `_capabilities.py` fails the drift test (US-1.1).
- **AC-2** The widened posting CHECK accepts posted / failed_post / reversed only for A-09's elimination clause or a non-attest client-ledger entry in a batch (US-1.1).
- **AC-3** Every CLS-07 and CLS-11 operation exists as a stub answering 501 behind its flag in the generated client (US-1.2).
- **AC-4** A breaking change to a posting, console or write-grant schema fails the consumer suites (US-1.2).
- **AC-5** The four gate kinds register and HOME-02 lists them (US-1.3).
- **AC-6** Batch approval re-classifies by code, writes one batch row and one human decision per entry, and attributes "Approved by RM under BH AJE thresholds v2" (US-2.1).
- **AC-7** A stale policy or entry answers 409 `snapshot_changed`; nothing is approved (US-2.1).
- **AC-8** Over-limit approval is refused `over_approval_limit`; request-approval opens a gate and a bell (US-2.2).
- **AC-9** Single approval writes at once with a 10 s Undo appending `approval_undone` (US-2.3).
- **AC-10** No agent or system context can approve, at three layers (US-2.3, INV-1).
- **AC-11** Reject with reason raises a CLS-06 issue; withdraw appends `approval_withdrawn`; editing an approved entry is `entry_locked` (US-2.4).
- **AC-12** Reasoning renders through `AgentText` with verified citations only (US-2.5).
- **AC-13** Posting runs a dry run first, needs fresh MFA, an `Idempotency-Key` and a 10 s grant (US-3.1).
- **AC-14** The workflow re-checks the five switches and the attest flag at consumption and fails closed with the reason (US-3.1).
- **AC-15** Each entry is written once (re-read by DocNumber and marker), read back and recorded insert-only (US-3.1).
- **AC-16** A failed entry fails alone, retries under its key, and the closing date is set only after all post (US-3.2).
- **AC-17** A read-back mismatch is `verify_mismatch`, flips the firm's kill switch and is corrected by a reversing entry (US-3.2).
- **AC-18** A closing-date conflict opens one conflict row with ask-client and re-date (US-3.3).
- **AC-19** Auto-reversals are Approved rows on the next close and post only with a person's batch (US-3.4).
- **AC-20** Without W1 the primary action exports a deterministic JE file and the entry reaches `recorded_externally` (US-3.5).
- **AC-21** Attest clients hold no write grant and every batch with an attest entry is refused at three layers (US-4.1).
- **AC-22** No route produces a policy-attributed decision (US-4.2).
- **AC-23** The firm switch needs security_admin and fresh MFA and is refused `write_capability_not_released` while the registry is off; the client owner grants and revokes with fresh MFA (US-5.1, US-5.2).
- **AC-24** The console reads health, the posting log and sync events; a walled user gets 404 (US-6.1, INV-3).

## 7. Task map
T02 bundle (AC-1, AC-5, AC-10) · T03 status words · T04 / T05 migrations (AC-2, AC-15, AC-21) ·
T06 stubs (AC-3) · T08 consumer tests (AC-4) · T09 seed · T12–T13, T17–T19, T22, T24, T30–T32,
T36 (S50+) the services and screens.

## 8. Deviations
- ADR numbers: the plan's ADR-161 (P-16) is ADR-344; its ADR-142 (P-13) is ADR-164.
- CLS-11's write-scope row drops "recategorizations · attachments" (Q2).
