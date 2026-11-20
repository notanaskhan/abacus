# POR-17 · Confirmation response

| Field | Value |
|---|---|
| Route and params | Portal host, no shell: `/confirm/$token` (the token travels in the path only, never a query string or a log line; the access log redacts it) |
| Template and host frame | T15 AuthCard single-page variant (720 wide, no portal nav) + T7-M reflow at 390 |
| Surface | public (link principal) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-17 Confirmation response - Granite Peak receivables -C2-/` |
| Epic and tasks | A-08 · SPEC-657 · A-08-T01 (contract), A-08-T05/T06 (stubs), A-08-T08 (content), screen rows per A-08 §9 |
| Persona | Rachel Imholt (Summit Trail Outfitters, AP); respondents of Alpine Ridge Sports, Canyon Basecamp, Front Range Bank |
| Flags | `confirmation_links` control (ADR-157) and `audits.confirmations` for the firm |
| Priority | P1 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

Every artboard is **built** (A-08 §2.1). Fixture-only parts are named in their row. 6 artboards. The flag-off row reads d's copy (the page never says why).

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Link opened | Summit Trail AP; firm letterhead, quoted authorization, invoice detail 138,200 + 151,750 + 122,650 = 412,600; Agree selected; partly filled | Fri Sep 25, 2026, 9:40 AM MT | E0 | D · **C locked** | planned · `por17.summit-trail` |
| b | Submitted | Receipt KV "Agrees · $412,600.00 · Sep 25, 2026 · 10:12 AM MT · r.imholt@example.com · Reference C2"; "This link no longer accepts changes" | Fri Sep 25, 2026, 10:12 AM MT | E0 variant | D · **C locked** | planned · `por17.summit-trail` |
| c | Does not agree | Alpine Ridge: $286,900.00 per client vs $282,600.00; difference $4,300.00 (amber-ink, read-only); CM-0628.pdf attached | Thu Sep 24, 2026 | E0 variant | D · **C locked** | planned · `por17.alpine-ridge` |
| d | Expired | Canyon Basecamp after `expires_at` (DV-9): "This confirmation link has expired" + call the firm on an independently found number; unknown and revoked tokens render the same (DV-7) | after `expires_at` | E0 variant | D · C report-only | planned · `por17.canyon-basecamp` |
| e | Already answered | "This confirmation was already answered on Sep 25, 2026." | Fri Sep 25, 2026, 2:00 PM MT | E0 variant | D · C report-only | planned · `por17.summit-trail` |
| f | Bank variant | Front Range Bank: revolver $6,500,000.00 + term loan $3,200,000.00; list every account with + Add account | Fri Sep 25, 2026 | E0 variant | D · **C locked** | planned · `por17.front-range-bank` |
| loading | — | skeleton per the template's loading grammar | — | — | D | planned |
| error | — | the read failed: designed error with Retry (chapter 10 §10.3 kind 10) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3); a client principal always 404 on confirmation routes | — | — | — | planned |
| flag off | — | C-20 "not turned on" state for the screen's flag; never a blank pane | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/POR-17/scenarios.ts` (A-08 §5.4), exported from the Python scenario (`make fixtures`, F-04-T31) and derived from the seed's footing figures, never typed by hand. Copy keys are `por17.<state>.<element>` in the screen's `copy.ts`.

## API

Every state reads this endpoint set (A-08 §4.3; stubs in A-08-T05 / T06):

- `GET /v1/confirm/{token}` (`confirmation.respond_view`, link principal, `link_scope_only`): state `open | expired | answered` and one confirmation's render data
- `POST /v1/confirm/{token}/code` · `…/code/verify` (`confirmation.respond_verify`; padded 202)
- `POST /v1/confirm/{token}/attachments` (`confirmation.respond`, email verified; ≤ 50 MB, DEC-58 types, scanned, write-once)
- `POST /v1/confirm/{token}/response` (`confirmation.respond`; 201 receipt, 409 `already_answered`, 403 `email_not_verified`)

Matrix actions from `permission-matrix/{sampling,workpapers,assurance,identity}.yaml` (A-08-T03): every adopt, accept, approve, decide, send and close is a person's (`agent: deny`); every client principal is denied.

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c, f | C (locked; A-08-T37) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/POR-17.spec.ts`) | b, c and f are not drawn in the gallery yet (the respondent's typing, other respondents' seeds): locked, unmeasured |
| d, e | C (report only) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/POR-17.spec.ts`) | — |
| host | D | — | portal page, T15-720 frame (Tier B) |

## Links

| From | To | Status |
|---|---|---|
| — | none: no portal navigation, no sign-in, no outbound links | — |

## Notes

Public, firm-controlled, link principal only. No portal nav, no sign-in, no client branding as sender, no payment language, no other customers' balances; "Accrued" never appears. Option tiles are a `radiogroup`; the CodeInput has six boxes with `autocomplete="one-time-code"`; the difference updates through `aria-live="polite"`; the attestation is a `switch`; Submit's disabled reason is in text; the expired page moves focus to its heading; reduced motion removes the 220 ms reveal; reflow at 390 px with no horizontal scroll.

## Deviations

- DV-7 unknown, revoked and expired tokens render the same expired copy with identical status and padded timing.
- DV-8 the respondent's typed CM-0628 and the attachment name are kept as submitted; AUD-14 cites CM-6281 (DF-34).
- DV-9 d and e clocks sit after `expires_at` and after the Sep 25 10:12 AM MT submission; README render times are capture artefacts.

## Acceptance

SPEC-657's criteria for this screen; each becomes a test named "POR-17 acceptance: <criterion>".
