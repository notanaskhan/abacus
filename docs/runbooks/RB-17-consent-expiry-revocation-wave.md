---
id: RB-17
title: Section 7216 consent expiry or revocation wave
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-04-16
---
# RB-17 · Section 7216 consent expiry or revocation wave

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 (one firm, agents paused per taxpayer); SEV2 if a wave lands inside a filing window |
| Linked from | `consent_expiring` notifications (ConsentLifecycleSweep, daily 6:00 AM CT), ADM-05's Expiring and Expired tiles, gateway refusals for condition 6 |
| SLO affected | none: preparation continues without agents |
| Kill switches that apply | none needed. The consent gate (gateway condition 6) is code and always on; it is never a rollout toggle (T-01 §2.1) |
| Rehearse by | R2 (Fri Apr 16, 2027) if tax is in scope; once on staging by notanaskhan before the Dec 31, 2026 wave |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Every agent read of tax return information needs a signed §7216 consent in force for that taxpayer
and tax year (ADR-231; C19). Consents expire (the template's stated expiry, else one year from
signing) and clients revoke them in writing. When many lapse together (the seed's 210 AI-use
consents all expire on Dec 31, 2026), agents pause for each of those taxpayers at once. Nothing
breaks: the work goes on by hand. This runbook keeps the firm working and gets consents renewed.

## 1. Recognise it
- Grace (or the firm's admin) and each requester get `consent_expiring` 30 days ahead, once per
  consent. ADM-05 shows the Expiring tile rising; on the day, Expired rises and the rows move up.
- Staff see the agents-off line on TAX-03 and the return screens ("prepared without agents") for the
  affected taxpayers; CLI-02 and CLI-05 show the consents row as expired or revoked.
- The audit trail shows `consent.expired` (sweep) or `consent.revoked` (a person's record), each
  followed by `access.changed`; gateway calls for those taxpayers are refused on condition 6.

## 2. Contain
Nothing to switch off. Each refusal is already scoped to one taxpayer and tax year; no cached
allowance survives `access.changed`. Do **not** grant anything to work around the gate: there is
no override, and asking a model to read without consent is a §7216 breach.

## 3. Preserve
- ADM-05 › Export CSV (`POST /v1/consents/exports`, fresh MFA): the register as it stood, from the
  sealed export bundle. Keep the export id in the incident note, not the file.
- For a revocation, the written revocation as received, uploaded as evidence on the client.

## 4. Assess
- How many taxpayers, which purposes (use, disclose to AI service providers, offshore), which tax
  years, and how many have returns in Gather or Prepare inside the next filing deadline.
- A revocation is final for that consent: never re-solicit unless the client asks. A declined
  consent blocks "Request consent…" (re-solicitation is refused by design).
- Offshore: a member's visibility of a client ends when any taxpayer entity's `offshore_disclosure`
  lapses (I-OFFSHORE). Check offshore staffing on those returns.

## 5. Notify
- Inside the firm: the tax partner and the client-service owners of the affected clients, with the
  ADM-05 filter link. No client data in chat; names stay in the product.
- Clients: only through the renewal envelopes (step 6). Services are never conditioned on
  consent; the envelope says so.

## 6. Recover
1. **Agents-off workflow (now).** Preparers carry on by hand. Returns for paused taxpayers show the
   agents-off line; reviewers sign off as usual. Nothing an agent drafted before the lapse is
   withdrawn; it stays a proposal a person decided on.
2. **Renew in one batch.** ADM-05 › filter Expiring (or Expired) › select › **Renew…**
   (`POST /v1/consents/renewals`): SIG-02 drafts one envelope per consent, keeping its purpose,
   recipient and year range. A person sends them from SIG-01 (batch the send; the envelope
   activities back off on a provider 429 at its Retry-After, N-02-T47).
3. **Paper or provider-off.** If the client signs on paper or outside the provider, record it
   (`POST /v1/consents/records`) with the signed copy as evidence.
4. **Revocations.** Record each in writing (`POST /v1/consents/{id}/revocations`). Nothing else.
5. As each envelope completes, the consent becomes `signed`, `expires_at` is set and the gate opens
   for that taxpayer and tax year on the next call. No restart, no deploy.

## 7. Verify
- ADM-05's tiles add to the total and Expired falls as renewals complete.
- For a renewed taxpayer, the agents-off line is gone from TAX-03 and a gateway call is admitted.
- For a revoked or still-expired taxpayer, a gateway call is still refused on condition 6.

## 8. Review
Typical actions: stagger expiries at the next renewal (a template's stated expiry spread across
months), start the renewal batch 45 days ahead of a known wave, and check the sweep's
`consent_expiring` reached every requester.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
