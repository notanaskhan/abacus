# POR-06 · Sign (portal)

| Field | Value |
|---|---|
| Route and params | Portal `/sign` (list) and `/sign/$envelopeId`; return page `/sign/$envelopeId/return?session=<uuid>`. Artboards: `/components/screens/POR-06?st=a…h` |
| Template and host frame | Portal shell P1, list → review → consent → provider view (DF-12) → return · `Wave 4 - Platform & Portal.dc.html#por06` |
| Surface | portal (never renders "Accrued"; the firm's name from branding, DEC-59) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-06 Sign - Ridgeline engagement letter/` · HANDOFF_VERSION 2026-10-21; DF-11 and DF-12 applied |
| Epic and tasks | N-02 · contract T05; stub T03; list and review T23; ERSD T24; provider view and return T26; KBA and joint filers T25, T27; dated letters T31; decline T28; download T29; 390 px T43 |
| Spec and ADRs | SPEC-381 AC-10..AC-12; ADR-149; ADR-146 (portal MFA) |
| Flags | `signatures.envelopes` (list, review); `signatures.esign_provider` (signing) |
| Manifest status | planned (portal paths are not in the firm tree, DEC-347); the portal entry mounts `/sign`, `/sign/$envelopeId` and `/sign/$envelopeId/return` since N-02-T26 (fixture data; live with T23) |

## States
| Artboard | Viewer | Clock | Data condition | Parity tier | Status |
|---|---|---|---|---|---|
| a | owen-calder | Mon Sep 14, 9:24 AM | Review: the letter Daniel Reyes sent at 8:40 AM; Continue unlocks on page 3 | C report; C lock before M10 | live with T23 |
| b | owen-calder | 9:24 AM | Sign step: ERSD accepted; identity and signature inside the provider's embedded view (DF-12) | C report (the provider frame masked) | live with T26 |
| c | owen-calder | 9:31 AM | Completed: the evidence record; countersign next | C report | live with T26 |
| d | owen-calder | 4:10 PM | 8879-PE: identity questions (KBA) in the provider view | C report (masked) | live with T25 |
| e | owen-calder | Fri Oct 2, 2026, 9:10 AM | Joint filers (Feld): Claire signed; Jonah signs with his own grant | C report | live with T25 |
| f | dana-kowalski | Tue Oct 6, 2026 | Rep letter dated Oct 9, the report date; signing opens that day (`before_date_as_of`) | C report | live with T31 |
| g | owen-calder | 9:24 AM | Decline: asks why; the envelope reads Declined | C report | live with T28 |
| h | owen-calder | 9:24 AM | Identity check failed (DF-11): no 24-hour lockout; "{firm} will send you a paper form to sign" | C report | live with T27 |

Non-artboard: flag off or not released to the provider ("{firm} will send this for signature soon"); not your turn; stale or expired session (return page re-checks); 390 px mobile (DEC-45).

## Built in N-02-T26 (part 1, fixture mode; DEC-1251)
Gallery `/components/screens/POR-06?st=a|b|c|pending|g|restricted|list` (`&w=390` for the phone), scenarios `apps/web/src/fixtures/scenarios/POR-06.ts` over `fixtures/handlers/portal-envelopes.ts`. Screen `apps/web/src/screens/POR-06/` on the T16 `SigningCeremony` kit; data `apps/web/src/domain/signing/portal.ts`.

| State | What renders |
|---|---|
| list | To sign (E13), then the Signed band: the 2025 Form 1065 letter and the two §7216 consents as separate rows |
| a | Review: steps Verify identity ✓ "Email code" · Review "Page n of 3" · Sign · Done; "Continue to sign" disabled with "Read to page 3 to continue." until page 3 has been half in view (progress posted per page) |
| b | ERSD: "Agree to sign electronically" with the binding-signature checkbox, "Agree and continue" (posts the disclosure version), then the provider's one-time view in the well (iframe; redirect gives one call to action). The artboard opens with the view already open |
| return, pending | `?session=` answered by the server: "Checking your signature" and polling every 3 s until `my_status` is `signed`; Completed never from the return alone |
| c | The completion card: "Signed. Thank you, Owen.", Document fingerprint "SHA-256 a41f…9c07", Signers "1 of 2 signed", "Waiting for 1 more signature." |
| g | Declined (red-tint pill), "Withdraw decline" restores the envelope; decline from a takes a reason (C7 codes) and a note |
| restricted | Not a signer (every read 404): "You aren't a signer on this envelope." |
| 390 | The kit's phone layout: step chips, full-width page, the step control as the 64 sticky footer |

## Copy (key strings; DF-11 text pending counsel)
| Key | String |
|---|---|
| `review.continue` | "Continue" (enabled on the last page) |
| `consent.title` | "Agree to sign electronically" (ERSD text is database content, counsel-approved) |
| `decline.title` | "Decline…" · reasons "I have questions" · "Something is wrong" · "Someone else should sign" · "Other" |
| `df11.paperForm` | "{firm} will send you a paper form to sign." **(pending counsel)** |
| `notReleased` | "{firm} will send this for signature soon." |

## Open gaps
- C7 v1's portal view names no other signer, no signed-at time and no verification record, so the completion card shows the fingerprint and the counts only (handoff c's "Verified by", "Method", "Next: Daniel Reyes countersigns"); N-02-T25 (C7 v1.1 additive) carries them.
- The ERSD disclosure text is database content with no portal read yet: part 1 shows the consent statement and records the version id only.
- Envelope header right side ("From Daniel Reyes · due Sep 24") and the "Signing order" card need the signer list (N-02-T25).
- d, e, f, h (KBA, joint filers, dated rep letters, DF-11) are T25, T27, T31; the Playwright walk, axe and the Tier C lock are N-02-T43.

## Links
Inbound: POR-02 home to-do, client signature-request email (secure link). Outbound: POR-02, signed-copy download.
