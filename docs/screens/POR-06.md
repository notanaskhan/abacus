# POR-06 · Sign (portal)

| Field | Value |
|---|---|
| Route and params | Portal `/sign` (list) and `/sign/$envelopeId`; return page `/sign/$envelopeId/return?session=<uuid>`. Artboards: `/components/screens/POR-06?st=a…h` |
| Template and host frame | Portal shell P1, list → review → consent → provider view (DF-12) → return · `Wave 4 - Platform & Portal.dc.html#por06` |
| Surface | portal (never renders "Accrued"; the firm's name from branding, DEC-59) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-06 Sign - Ridgeline engagement letter/` · HANDOFF_VERSION 2026-10-21; DF-11 and DF-12 applied |
| Epic and tasks | N-02 · contract T05; stub T03; list and review T23; ERSD T24; provider view and return T26; KBA and joint filers T25, T27; dated letters T31; decline T28; download T29; 390 px T43 |
| Spec and ADRs | SPEC-381 AC-10..AC-12; ADR-149; ADR-146 (portal MFA) |
| Flags | `signatures.envelopes` (list, review); `signatures.docusign` (signing) |
| Manifest status | planned; `fixture` with T23; `live` with T26 |

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

## Copy (key strings; DF-11 text pending counsel)
| Key | String |
|---|---|
| `review.continue` | "Continue" (enabled on the last page) |
| `consent.title` | "Agree to sign electronically" (ERSD text is database content, counsel-approved) |
| `decline.title` | "Decline…" · reasons "I have questions" · "Something is wrong" · "Someone else should sign" · "Other" |
| `df11.paperForm` | "{firm} will send you a paper form to sign." **(pending counsel)** |
| `notReleased` | "{firm} will send this for signature soon." |

## Links
Inbound: POR-02 home to-do, client signature-request email (secure link). Outbound: POR-02, signed-copy download.
