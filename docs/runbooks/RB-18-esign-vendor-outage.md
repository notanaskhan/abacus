---
id: RB-18
title: E-signature or knowledge-based-authentication vendor outage (record mode; wet-signature path)
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-08-16
---

# RB-18 · E-signature or KBA vendor outage

Written for DocuSeal (ADR-342; N-02-T46, DEC-1679). Accrued sends envelopes through each firm's own
DocuSeal install; record mode (importing a package signed elsewhere) needs no provider. Rehearsed
once by notanaskhan on staging with the synthetic test firm (PF-X1) before M13.

| Field         | Value |
| ------------- | ----- |
| Owner         | AY (partner-facing); N for provider health, flags and installs |
| Severity      | SEV2 when sending is down in a live window or an 8879 deadline week; SEV3 otherwise |
| Applies       | from M11 (letters and consents through DocuSeal); from M13 (Tue Aug 31, 2027) for the 8879 family, whose identity check is the provider's |
| Kill switches | `signatures.esign_provider` per firm (off: sending stops cleanly, record mode stays); a firm's DocuSeal install (`esign_install disconnect` also erases its key); W7 in the write-capability registry for everyone |
| Linked from   | send errors `provider_unavailable` on SIG-02; envelopes stuck in Sent after the status poll; DocuSeal's status page |

## 1. What keeps working in an outage

- **Record mode** (import a package already signed elsewhere): no provider involved. SIG-01
  "Import signed package…" and the envelope drawer keep working.
- **Wet signature**: a signer who cannot sign electronically signs on paper; the firm records it on
  the envelope (`POST /v1/envelopes/{id}/signers/{sid}/wet-signature`, `envelope.record_wet_signature`)
  or imports the scanned, signed document in record mode.
- **KBA failures** (DF-11): after three failed KBA attempts the signer is routed to a handwritten
  signature, never a 24-hour lockout; an outage takes the same path.

## 2. During an outage

1. Confirm on the provider's status page and in our send errors; declare SEV2 if sending is down
   in a live window (`docs/ops/on-call.md`).
2. `signatures.esign_provider` off for the affected firms (`make flag`, the other founder approving):
   new sends stop cleanly instead of failing one by one.
3. Tell the firms: letters due now go out from their own tool or on paper, and come back into
   Accrued by record-mode import (`docs/ops/pilot/import-signed-letters.md`).
4. Envelopes already out: they stay as they are; reminders pause with the flag. After recovery,
   check each envelope's status against the provider before turning the flag back on.
5. For an 8879 near a filing deadline: the handwritten path (DF-11): the signer signs the
   authorization on paper, the firm records it on the envelope (wet signature) with the scan as
   evidence; the amount binding and the transmission gate treat it like an electronic signature.
   RB-19 if the engine bridge is also at risk.
6. **Rate limits, not an outage:** a 429 from DocuSeal is retried no sooner than its Retry-After
   (N-02-T47, DEC-1673); a surge drains on its own. Act only if sends stay queued past an hour.
7. **Messages to clients** go from the firm's own templates, which are database content edited in
   the firm's template screens (ADM-10, POR-20), never text in git: the firm picks its "we'll send
   your documents on paper" template and sends it as a person.

## 3. A firm's DocuSeal install (TASK-2152; DEC-1279)

A firm sends through DocuSeal only with a connected install whose sealed secret holds the API key,
its `signatures.esign_provider` flag on, and W7 open. The install is the operator's, through an
ops request (`ops-task.yml`; staging: the ops one-off, `infra/README.md`). The key never appears
in the request: the task reads it from its secret store (`ABACUS_ESIGN_INSTALL_API_KEY`).

- **Connect:** `abacus_tools.esign_install connect --tenant <id> --requested-by <member user id>
--operator <handle>`. DocuSeal is asked first whether the key works; a refusal writes nothing.
- **Key compromised or rotated at DocuSeal:** put the new key in the secret store, then
  `esign_install rotate`. The old sealed copy is erased in the same unit of work.
- **Stop one firm sending now:** turn the firm's `signatures.esign_provider` flag off (the kill
  switch); `esign_install disconnect` also erases the key. Open envelopes keep their state; the
  status poll stops reaching DocuSeal for that firm.
- **Check:** `esign_install status` prints `connected` or `none`, never the key.

## 4. After recovery

1. Turn the flag back on for one firm first; send one synthetic envelope on staging (PF-X1) and
   watch it reach Sent and Viewed.
2. The status poll is the truth (the webhook is a hint): every open envelope's state is re-read
   from DocuSeal on its next poll, so missed webhooks need no replay.
3. Reminders resume with the flag; check SIG-01's reminder history for each envelope that was
   due a reminder during the outage and send it as a person if it is still needed.

## 5. Verify
- SIG-01's Out tab counts match DocuSeal's for each firm; no envelope stays Sent with a completed
  submission at the provider.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
