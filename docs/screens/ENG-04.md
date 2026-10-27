# ENG-04 · Engagement letter composer

| Field | Value |
|---|---|
| Route and params | `/engagements/$engagementId/letter` (Engagement record › Letter). Artboards: `/components/screens/ENG-04?st=a…f` |
| Template and host frame | T3 document composer (clauses rail · document · facts) · `Wave 2 - Engagements.dc.html#eng04` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ENG-04 Engagement letter composer - Ridgeline cost segregation and -754/` · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | N-02 · contract T05; stub T03; letter versions T32; composer T33, T34; approval and send T35; amend T37 |
| Spec and ADRs | SPEC-381 AC-13..AC-15; ADR-149; ADR-167 (§7216 consents) |
| Flags | `engagements.letter_composer` (T32; until then `signatures.envelopes`); flag off: the record panel (`letter.record`) |
| Manifest status | planned; `fixture` with T33; `live` with T35 |

## States
Clock Mon Sep 14, 2026, 8:35 AM CT; viewer Daniel Reyes (engagement partner).

| Artboard | Data condition | Parity tier | Status |
|---|---|---|---|
| a | Partner approved: two non-standard clauses flagged; ready to send to Owen Calder | C report | live with T35 |
| b | Draft: watermarked; the primary asks for partner approval | C report | live with T33 |
| c | Sent: E13 out, read-only, "0 of 2 signed" | C report | live with T35 |
| d | Signed (Copperleaf 2026 Close): locked, approver of record, SSARS routing note | C report | live with T35 |
| e | Audit variant (Fairhaven): AU-C 210 clauses, sent Sep 8, "0 of 2 signed" | C report | live with T34 |
| f | Bundled consents (Feld): the two §7216 consents are separate documents, each signed (AC-15) | C report | live with T35 |

Non-artboard: an edit after approval stales it (`letter.approval_staled`, the chip returns to Draft); recorded letter (`mode = recorded`, the kept record panel); flag off (record panel only).

## Status
`letter` codes (DF-31): Not started, Draft, Partner approved, Sent, Signed, Not required this year, Superseded.

## Copy (key strings)
| Key | String |
|---|---|
| `primary.requestApproval` | "Request partner approval" |
| `primary.approve` | "Approve" (partner; fresh second factor) |
| `primary.send` | "Send for signature" |
| `chip.signedCount` | "{signed} of {total} signed" |
| `consents.separate` | "Consents are signed as separate documents." |

## Links
Inbound: ENG-02 G3 row, ENG-01 "Letter │ Not signed" filter. Outbound: SIG-02 (send), SIG-01, FIL-01 (signed copy).
