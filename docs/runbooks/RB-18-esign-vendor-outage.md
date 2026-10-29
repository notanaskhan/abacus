---
id: RB-18
title: E-signature or knowledge-based-authentication vendor outage (record mode; wet-signature path)
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-08-16
---
# RB-18 · E-signature or KBA vendor outage

**First notes (N-02-T17, for AY).** The full runbook lands with DocuSign (N-02-T18 onward, before
M11, Tue Aug 17, 2027); until then only record mode is live and an outage cannot stop a signature
Accrued sends, because Accrued sends none.

| Field | Value |
|---|---|
| Owner | AY (partner-facing); N for provider health and flags |
| Applies | from M11 for DocuSign embedded signing; from M13 (Tue Aug 31) for KBA on Form 8879 |
| Kill switches | `signatures.docusign` (off: sending stops, record mode stays), `signatures.kba_8879` (off: 8879 KBA stops; DF-11's handwritten path stays) |
| Alarms | provider health (to wire with N-02-T18: the provider's status feed and our send error rate) |

## 1. What keeps working in an outage
- **Record mode** (import a package already signed elsewhere): no provider involved. SIG-01
  "Import signed package…" and the envelope drawer keep working.
- **Wet signature**: a signer who cannot sign electronically signs on paper; the firm records it on
  the envelope (`POST /v1/envelopes/{id}/signers/{sid}/wet-signature`, `envelope.record_wet_signature`)
  or imports the scanned, signed document in record mode.
- **KBA failures** (DF-11): after three failed KBA attempts the signer is routed to a handwritten
  signature, never a 24-hour lockout; an outage takes the same path.

## 2. During an outage (from M11; draft)
1. Confirm on the provider's status page and in our send errors; declare SEV2 if sending is down
   in a live window (`docs/ops/on-call.md`).
2. `signatures.docusign` off for the affected firms (`make flag`, the other founder approving):
   new sends stop cleanly instead of failing one by one.
3. Tell the firms: letters due now go out from their own tool or on paper, and come back into
   Accrued by record-mode import (`docs/ops/pilot/import-signed-letters.md`).
4. Envelopes already out: they stay as they are; reminders pause with the flag. After recovery,
   check each envelope's status against the provider before turning the flag back on.
5. For an 8879 near a filing deadline: the handwritten path (DF-11) and RB-19 (tax-engine bridge)
   if the deadline is at risk.

## 3. Notes to complete with N-02-T18 and T22
- The alarm names and thresholds; the provider's status feed.
- How undelivered webhooks are replayed after recovery (the envelope workflow's signals).
- The firm-facing words for an outage notice (a status-page component per provider).
