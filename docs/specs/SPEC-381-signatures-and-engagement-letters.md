---
id: SPEC-381
title: "Signatures and engagement letters: record mode, the C7 envelope service, DocuSign embedded signing, the e-file authorization policy and the letter composer (N-02)"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-031, ADR-149, ADR-150, ADR-152, ADR-158, ADR-161, ADR-167]
related_specs: [SPEC-025, SPEC-380]
created: 2026-10-27
updated: 2026-10-27
---

> **Instructions for coding agents**
> - The epic in full is `docs/plan/epics/N-02.md`; where it and this spec differ, this spec wins (§11).
> - Every test names the AC it proves. ADR-149 binds the signature path; it supersedes SPEC-025 Q2.

## 1. Summary
Firms get one place to send, track and prove signatures: the signatures hub (SIG-01), the envelope builder (SIG-02), portal signing (POR-06) and the engagement-letter composer (ENG-04). **Record mode first:** a firm imports a package signed in its own tool, with the signer facts and an attestation, and Accrued keeps the evidence. **Then DocuSign embedded signing** with ID Verification (KBA) behind an `EnvelopeProvider` port, the first write capability (W7). Envelope policies are data; sending is a person's act.

## 2. Problem and context
Engagement letters, §7216 consents, Forms 8879 and 2848, rep letters and governance letters are signed outside Accrued today; their evidence sits in email and the firm's provider. Gates G3 (letter signed) and the e-file authorization need a signed record that Accrued can prove. The IRS requires KBA for remote 8879 signing (Pub 1345) and forbids SMS as the identity factor for the 8879 family.

## 3. Actors
| Actor | Role |
|---|---|
| Manager, engagement partner, `client_service` (Grace Holloway) | Draft, send, remind, void, import record-mode packages, record a wet signature |
| Engagement partner | Approves the letter (fresh MFA); countersigns when named |
| Security admin | Tightens envelope policies (stricter only, fresh MFA) |
| Portal signer (owner, contributor, taxpayer, spouse) | Reviews, accepts ERSD, signs or declines their own envelopes (`scope_only`) |
| Accrued Agent | May **draft** an envelope or letter; never sends, reminds, voids, imports, approves or signs |

## 4. Goals and non-goals
**Goals:** record mode (import a signed package); the C7 envelope service; DocuSign embedded signing with KBA for the 8879 family; reminders, expiry, void and decline; firm countersignature; the letter composer with partner approval; signed copies filed as client-scoped files (ADR-158); per-signer evidence packages in the records bucket.

**Non-goals:** a native signing ceremony or bought KBA vendor (2028); SMS identity for the 8879 family (never); model-drafted letter wording, messages or reminders (DEC-79 off); DocuSign's own client emails (captive recipients).

## 5. Acceptance criteria

### Record mode (SIG-01 r; DF-12; DEC-64)
- **AC-1** Given a person with `envelope.import_record`, when they import a signed package with its signer facts (names, signed dates, identity method) and attest it, then an envelope with `provider = 'record'` and status `completed` is created, each file is scanned, hashed and stored as an evidence version, the signed copy is filed under the client's Signed authorizations folder, and `envelope.imported` is audited.
- **AC-2** A record-mode envelope answers the same gate facts as a provider envelope (G3 for an engagement letter).
- **AC-3** The agent and the system are refused `envelope.import_record` (403).

### The hub and evidence (SIG-01 a–g)
- **AC-4** `GET /v1/envelopes` lists envelopes the viewer can see under `visible()` (client scope included), with tabs To send, Out, Completed, Expired, and wall-safe counts (DEC-43).
- **AC-5** The drawer shows per-signer evidence: signed time, masked IP, identity result, signature method; revealing the IP needs `signer.reveal_ip`, a fresh second factor and onshore access, lasts 10 seconds and is audited.
- **AC-6** The evidence download is a zip of per-signer packages, the certificate and a manifest of SHA-256 hashes, audited.

### Sending and policies (SIG-02; W7)
- **AC-7** Send is human-only: it consumes a single-use approval grant with `not_before = +10 s`; Undo voids the grant and audits `envelope.send_undone` (ADR-161).
- **AC-8** An envelope of policy family `efile_authorization` (every `form_8879*`) requires KBA, at most three attempts, and the wet-signature failure path; no `sms_code` identity method exists.
- **AC-9** A security admin may only tighten a policy; a looser PUT is refused 422.

### Portal signing (POR-06)
- **AC-10** A signer sees only their own envelopes; the ERSD consent is accepted and stored before the first signing session; a signing session is one-time and short-lived and refused `not_your_turn`, `before_date_as_of`, `declined`, `verification_failed` or `mfa_required`.
- **AC-11** Three failed KBA attempts close the remote path, mark the signer `verification_failed`, and SIG-01 reads "Needs a handwritten signature" with "Upload signed 8879…" (DF-11); POR-06 tells the signer the firm will send a paper form.
- **AC-12** Decline takes a reason and may be withdrawn while the envelope is open.

### Letters (ENG-04)
- **AC-13** The composer drafts from a template version with clause toggles, typed variables and plain-text overrides; a partner approves with a fresh second factor against the content hash; any edit after approval stales it (`letter.approval_staled`).
- **AC-14** Sending a letter creates a C7 draft from the `engagement_letter` source; the existing record path (`letter.record`) stays.
- **AC-15** §7216 consents are separate signed documents, never letter clauses.

### Cross-cutting
- **AC-16** Every final verb (send, remind, void, import, wet signature, countersign, approve, sign) denies `agent` and `system` (I-AGENT-NEVER).
- **AC-17** Envelope events and signature evidence are insert-only; signed packages are written with Object Lock retention (ADR-004).
- **AC-18** With `signatures.envelopes` off every route answers 404; flag-off states are designed (SIG-01 record-mode rows only; POR-06 "{firm} will send this for signature soon"; ENG-04 the record panel).
- **AC-19 Record-mode readiness (N-02-T17).** Given `signatures.envelopes` on for synthetic firms (the scenario load, staging and local) and for the canary, then record mode is walkable on the production canary by Fri May 28, 2027; a firm's existing signed letters are imported per `docs/ops/pilot/import-signed-letters.md`; `docs/ops/gates/M10-client-facing.md` carries the "letters at least in record mode" row; RB-18 has its first notes.

## 6. State transitions (envelope)
| From | Event | To | Who |
|---|---|---|---|
| — | draft created | draft | person or agent (`envelope.draft`) |
| draft | sent (after the grant's 10 s) | sent | person (`envelope.send`) |
| sent | a signer viewed | viewed | signer |
| sent, viewed | some signers signed | partially_signed | signers |
| any open | all signers signed (and countersign) | completed | signers |
| any open | a signer declined | declined | signer |
| any open | expiry passed | expired | system |
| draft, sent, viewed, partially_signed | voided with a reason | voided | person (`envelope.void`) |
| — | record-mode import | completed | person (`envelope.import_record`) |

## 7. Data
Tables per `docs/plan/epics/N-02.md` §4.2 (`signatures_v1`, N-02-T07; `engagement_letter_versions`, T32). Classification: `ip_sealed`, `decline_note`, `email_at_send` restricted or confidential as listed there; no SSN or TIN in any signer packet.

## 8. API
`docs/contracts/c7-envelopes.md` (C7 v1; stub with N-02-T03). Webhook receiver `POST /v1/webhooks/docusign-connect` only after the ADR-152 amendment is accepted (N-02-T19).

## 9. Permissions
`docs/architecture/permission-matrix/signatures.yaml` (N-02-T02) and the letter rows in `engagements.yaml`. Human-only: `envelope.send`, `envelope.remind`, `envelope.void`, `envelope.import_record`, `envelope.record_wet_signature`, `envelope.countersign`, `letter.approve`, `letter.send`, `letter.amend`, and every portal signing verb.

## 10. Audit events
As `docs/plan/epics/N-02.md` §4.6, identifiers only.

## 11. Differences from the epic, and decisions
- ADR-149 (P-26) accepted 2026-10-27 by the builder (AMENDMENT-solo, DEC-706). Its counsel fallback stands: the DocuSign path stays behind `signatures.docusign` until counsel answers and F-09-T41's go/no-go; record mode does not wait.
- The P-45 amendment (the provider webhook receiver) is drafted into ADR-152, still proposed (DEC-707); decide-by Fri Jun 11, 2027. If refused: poll only.
- Solo edition: no CODEOWNERS lines; `protected-paths.md` lists `modules/signatures/` (N-02-T02).

## 12. Task plans
T02 protected bundle · T03 C7 stub · T04 consumer tests · T05 screen contracts (S13) · T06 DF-12 spike (throwaway, needs the DocuSign demo account) · T07 migration `signatures_v1` · T08–T09 record-mode import and gate facts · T11–T15 hub, drawer, evidence · T18–T22 W7 adapter, poll, sends · T23–T29 portal signing, KBA, wet signature · T30–T31 builder, dated letters · T32–T37 letter composer · T38–T44 evidence verify, journeys, parity, rollout.

## 13. Open questions
None open for S13.
