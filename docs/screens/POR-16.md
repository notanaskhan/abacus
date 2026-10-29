# POR-16 · Connections · Copperleaf

| Field | Value |
|---|---|
| Route and params | None yet: fixture mode only. A-02-T28 adds `/account/connections` in the portal entry (back chip "‹ Home" until POR-12, N-03) and the live swap. Artboards: `/components/screens/POR-16?st=a…g` |
| Template and host frame | T7 reduced (F-05 `PortalLayout variant="reduced"`: one centred pane 720 under the full PortalToolbar, no item active) and T7-M at 390 · `Wave 3 - Client Portal.dc.html#por16` |
| Surface | portal (white-labelled; the client sees the firm's name, never "Accrued") |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-16 Connections - Copperleaf/` (README.md, spec.md, revision.md R2) |
| Epic and tasks | A-02 · contract stub and fixtures A-02-T06 (C20 v1); service A-02-T16; frontend in fixture mode A-02-T18; live swap A-02-T28; parity A-02-T31 |
| Manifest status | built on fixtures (A-02-T18, 2026-10-27): every Copperleaf artboard in the gallery; the manifest entry stays `planned` with a null path until A-02-T28 |

Code: `apps/web/src/screens/POR-16/{index.tsx, copy.ts, scenarios.ts, POR16.test.tsx}` over `fixtures/scenarios/POR-16.ts`, `fixtures/seed/connections.ts` and `fixtures/handlers/connections.ts` (A-02-T06).

**White label and read-only (AGENTS frontend rule 7, DEC-01, ADR-040, DF-19).** No "Accrued", no posting scope or copy ("post entries you approve", "post approved entries", the Approvals note are masked until P-16), no password field (sign-in happens on the provider's site), no vendor logo or brand colour (Lucide glyph tiles on the category colour: olive ledger, espresso bank and payroll, clay card, ochre sales).

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Back chip "‹ Account" | POR-12 (N-03) | planned; reads "‹ Home" to the portal home until POR-12 lands (A-02 §11.2 Q4) |

## States

| Artboard | Scenario | What it shows |
|---|---|---|
| a | `a` (Mon Sep 14, 9:24 AM) | QuickBooks Online "Connected by Tess Moreno · Mar 4, 2026 · last sync 9:15 AM" · Read ledger; Front Range Bank ••4410 "Bank feed · daily · last sync 6:02 AM"; American Express ••1009 Needs reauth with Reconnect; Square connected; Shopify and Payroll provider Not connected |
| b | `b` | a with the O3 consent sheet "Reconnect American Express": will, won't, the authorization toggle; *Continue to American Express* disabled until it is on |
| c | `c` (9:30 AM) | the Amex card Connecting… |
| d | `d` (9:31 AM) | "reconnected by Tess Moreno · Sep 14, 9:31 AM" |
| e | `e` (Wed Mar 4, 2026) | the first QuickBooks connect: "Brightwater Hale will read your ledger", read-only (DF-19) |
| f | `f` | the 420 Dialog "Disconnect QuickBooks Online?" (the kit's `sm`; the handoff draws 400) |
| g | `g` | Square Needs attention · "Last sync failed Sep 13 · Try again" |
| 390 | `a` with `mobile` | status under the name, actions as full-width 44px buttons |
| empty, loading, error, not allowed | handlers | "Brightwater Hale hasn't asked to connect any systems"; skeleton rows; the error with Try again; a 404 entity |

h and i (Tessellate, HR and ticketing) are X-02's.

## Rules

- Status words are the C2 registry's `integration` codes in the portal's wording (`available` reads "Not connected").
- *Export instead* sits beside every ledger card's Connect; a ledger with no adapter here offers only it (ADR-108). Until A-02-T28 resolves the open trial-balance request it says the team will ask when it needs one.
- The consent sheet's title, lists, toggle sentence, button and helper are catalogue content (`card.consent`); this screen writes none of them.
- Client actions (Connect, Reconnect, Disconnect) appear only when the card's `allowed_actions` carries them.

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, c, d, g | C (threshold 0.20, maxDiffPixelRatio 3 %) | 2.23 / 1.85 / 2.04 / 2.03 | locked (A-02-T31, measured Thu Oct 29, 2026); the DF-19 copy differences are a recorded deviation (the parity spec applies no masks yet) |
| b, e, f | C | 16.62 / 17.89 / 7.77 | report-only: the sheet (b, e) and the dialog (f) over the page, plus the DF-19 rewording; not locked |
| host | D | — | one pane 720 under the portal toolbar, no rail: holds (a, c, d, g) |
| h, i | — | — | X-02 |

## Deviations
| Where | Handoff | Built | Why |
|---|---|---|---|
| Relationship caption | "reads your books and posts only the entries you approve" | "reads the books you connect. Nothing in your accounting system changes." | DF-19 (A-02 §5.4) |
| f body | "…or post accepted entries. Your August close may be delayed." | "…won't be able to read your books. What it already received stays in your client file." | DF-19; A-02 AC-9.5 |
| e scopes | Read ledger · Post approved entries | Read ledger | DF-19 |
| Back chip | "‹ Account" | "‹ Home" | POR-12 is N-03's (A-02 §11.2 Q4) |
