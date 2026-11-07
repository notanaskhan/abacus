# NOT-03 · Response letter editor & approval · CP2000 · TY2024 · Whitley

| Field | Value |
|---|---|
| Route and params | `/notices/$noticeId/response` · `?ov=mark-sent` (O3) · `?ov=agency-reply` (O3) · `?ov=signoff:<level>` (SHL-12) |
| Template and host frame | T10 DocumentOnWell, structure 470 · paper 896 (F-06-T14, F-06-T15) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/NOT-03 Response letter editor and approval - CP2000 - TY2024 - Whitley/` |
| Epic and tasks | N-04 · stubs T02 · screen T20 · response T12, T16 · C7 additive T08 · E2E T26 |
| Manifest status | live (N-04-T22); contract final at N-04-T27 (2026-11-07): changes go through a new contract version |

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | samuel-ito | Mon Sep 14, 2026, 10:02 AM | 10:02 | Draft in review: DRAFT watermark; Prepared KO ✓ · Reviewed SI in progress · Approved DR ring; "Approve…" records L2 and routes to Daniel | fixture (T20) |
| b | daniel-reyes | 10:14 AM | 10:14 | Approved: green-tint Approved; watermark gone; "Send for client signature…" → SIG-02 d | fixture (T20) |
| c | samuel-ito | 10:02 AM | Sep 15 | Out for signature: envelope pill "Sent · 0 of 2 signed"; paper read-only; strip "Waiting on Marcus and Dana (POR-06) · payment pending" | fixture (T20) |
| d | samuel-ito | 10:02 AM | Sep 16 | Ready to send: both signed; Direct Pay confirmation accepted; enclosure 4 on; "Mark as sent…" | fixture (T20) |
| d2 | samuel-ito | 10:02 AM | Sep 17 | Mark as sent sheet: IRS Documentation Upload Tool, confirmation number, sent Sep 17, 2026; follow-up 60 days | fixture (T20) |
| e | samuel-ito | 10:02 AM | Sep 17 | Awaiting IRS: "Follow-up Nov 16, 2026 · Kevin Osei"; Activity "Response sent via DUT · confirmation •••• 4821" | fixture (T20) |
| f | samuel-ito | 10:02 AM | Dec 2 | Resolved: "Closed Dec 2, 2026 · agreed amount assessed and paid" | fixture (T20) |
| g | samuel-ito | 10:02 AM | 9:24 | Approval blocked: "Approve…" disabled, "Waiting for the partner's decision (NOT-02)" | fixture (T20) |
| composed | as a | — | — | Log IRS reply… (Resolved or Escalated); Escalated; Regenerate confirm; Position mismatch ("Regenerate for Disagree"); envelope Declined / Expired; signed copy in record mode | composed (DEC-32) |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/notices/{id}/response` | `ResponseOut` | `notice.read` | `locked` after send |
| write | `PUT /v1/notices/{id}/response` · `/regenerate` | `ResponseOut` | `notice_response.edit` | 409 `stale_version`, `response_locked` |
| write | `POST /v1/sign-offs` (P-04) | sign-off | `sign_off.*` | 409 `decision_pending`, `position_mismatch`, `explanation_required` |
| write | `POST /v1/notices/{id}/response/send-for-signature` | `SendForSignatureOut` | `notice_response.send_for_signature` | manager reviewer or signer |
| write | `POST /v1/notices/{id}/response/mark-sent` | `SentOut` | `notice_response.mark_sent` | client service, managers; 409 `not_ready` |
| write | `POST /v1/notices/{id}/agency-replies` | `NoticeOut` | `notice.agency_reply` | preparer function and above |

## Status
`notice`, the derived `notice_response_readiness`, C7's envelope words.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Approvals discs | SHL-12 | live (P-04) |
| Send for client signature… | SIG-02 d | live (N-02) |
| Payment row | the request in the client's portal (POR-06) | live; POR-10 is planned (R-03) |
| Position | NOT-02 decision | live |

## Deviations
1. Letters come from a firm template in the database; "Regenerate" refreshes template paragraphs from current figures and keeps human edits ("Keeps your edits; refreshes the template paragraphs"). Agent-drafted paragraphs need ADR P-25.
2. The c strip reads "payment pending" and the payment row links to the request in the client's portal, not POR-10 (R-03).
3. The signed letter never changes (R-06, ESIGN/UETA; ADR-004): d's paid date shows in the Payment band and enclosure 4, never in the signed copy (QN-4).
4. Edit is per-paragraph plain text with an edited mark (F-06-T15); the rich-text editor waits for ADR P-59.

## Acceptance
- NOT-03 acceptance: no Response sent without the taxpayers' signatures and an accepted payment confirmation where one is due.
- NOT-03 acceptance: the follow-up is Nov 16, 2026 (60 days after Sep 17).
- NOT-03 acceptance: the confirmation shows as •••• 4821 only.

## Figures
Whitley: 686.40 tax, 66.61 interest, 753.01 total; sent Sep 17, 2026; follow-up Nov 16, 2026.
