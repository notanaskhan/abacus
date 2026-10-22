# SHL-01 · Firm app shell · toolbar and nav

| Field | Value |
|---|---|
| Route and params | None of its own: chrome over every firm route under `appRoute` (`legacy/Layout.tsx`). Artboard: `/components/screens/SHL-01?st=a…g` (gallery builds) |
| Template and host frame | C-00 Shell Kit `Toolbar` in `AppShell` (README T2) · `Wave 0 - Shell.dc.html#shl01` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-01 Firm app shell - toolbar and nav/` · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-01 · P-01-T02 (TASK-396); docs with Deviations P-01-T17 |
| Manifest status | fixture |

Code: `src/shell/firm/ToolbarData.tsx` (`useFirmToolbar`), `src/app-core/nav-areas.ts` (the 13 areas, landings, chords, `activeArea`), `src/shell/firm/{hotkeys.ts, InterimGo.tsx, InterimSupport.tsx, copy.ts}`, `src/routes/firm/areas.tsx` (Engagements index and the flag-off landings), `src/screens/SHL-01/{index.tsx, scenarios.ts, copy.ts, SHL-01.test.tsx}`.

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc | Mon Sep 14, 2026 9:24 AM CT | E0 | Any firm route, `/` → Home lit; `unread_count` 4 → dot | built · fixture |
| b | hannah-leclerc | same | E0 | Open screen is a landing (HOME-01 … SIG-01) → its manifest `navArea` is lit; 13 strips at 1400 | built · fixture |
| c | hannah-leclerc | same | E0 | Pointer and keyboard: hover Audits, focus-visible Inbox, Go… pressed (held with `forceState` in the artboard) | built · fixture |
| d | hannah-leclerc | same | E0 | `unread_count` 0 → no dot, name "Notifications" | built · fixture |
| e | hannah-leclerc | same | E0 | Bar width: 1400 → Signatures in More; 1279 → Signatures, Closes, Audits in More (DF-39 More first, measured) | built · fixture |
| f | hannah-leclerc | same | E0 | Route `/settings/*` (and legacy `/admin/*`) → nothing lit, firm pill pressed | built · fixture |
| g | hannah-leclerc | same | E0 | Open screen ENG-10, HOME-05, INS-01, BND-04, WB-12, KNW-06, FSP-01, ATT-01 → its `navArea`; Go… tooltip | built · fixture |

Loading: the toolbar draws at once; the dot is absent until `unread_count` answers, and the firm pill is empty until `/v1/me` does. Error: a failed notifications read leaves no dot (never a number). Not-allowed: none; every firm user sees the same 13 items.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/me` | `MeOut` (active membership `firm_name`) | — | — |
| read | `GET /v1/notifications?limit=50` (v1) | `NotificationPageOut.unread_count` | `OWN` | every firm user; polled 60 s and on window focus (DEC-23) |
| read | `GET /v1/me/capabilities` | `flags.palette` | — | fails closed: no R2 tooltip line |

The v2 envelope (`days=30`, tabs, counts) is P-01-T01; the toolbar reads only `unread_count`, which v1 already returns.

## Status
None. The bell is a dot, never a count (D4).

## Copy
Toolbar labels: `shell/nav.ts` (scope-guards). "Go to anything ⌘K", "Also: New to-do… · Load saved prompt… · Open board" (Toolbar kit). Panes "Overview" (spec). R2 strip labels: `screens/SHL-01/copy.ts`. Interim frames (undesigned, DEC-32 pattern): `shell/firm/copy.ts`; the shortcut list is SHL-03's.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Nav item | landing screen path, or the area's flag-off page while it has none (`app-core/nav-areas.ts`) | HOME-01 `/` (legacy), ENG-01 `/engagements` (legacy), KNW-01, CLI-01 legacy; the other 9 planned |
| Go… / ⌘K | SHL-02 | planned (interim O5 frame) |
| Firm pill | SHL-03 | planned (legacy menu) |
| Support | SHL-05 | planned (interim O2 frame) |
| Bell | SHL-04 | planned (legacy drawer) |

## Acceptance
- SHL-01 acceptance: the nav still reads the same 13 items in the same order; the 1400 width test and its fallbacks are unchanged.
- SHL-01 acceptance: frame g shows eight strips; every new area lights an existing nav item.
- SHL-01 acceptance: the Go… tooltip shows the second line with the three actions (once the `palette` flag exists; AC 1.1.8).
- SHL-01 acceptance: the bell stays a 6px brick dot with no count.
- Parity: `shl-01a.toolbar` Tier A (0.11 % at the first run); Tier D toolbar 46, item 32, pills 30, bell 30 × 30, dot 6, Geist 13.5, and the 13 strips of b at 1400 (`e2e/visual/tier-d.spec.ts`).

## Figures
None.

## Deviations
- SHL-01a.png holds frame a only (the README calls it "b · 13 strips"). One Tier A crop exists, the Home-lit toolbar at 1400; the 13 strips of b are held by Tier D (width, step, firm name) and the state tests (lit item per strip), with no PNG to compare.
- DF-39 order: the app uses `moreFirst` (Signatures, then Closes and Audits into More before the pill shortens), as SHL-01a and P-01 AC 1.1.4 draw it; the kit's default ladder (short name first) stays for its specimens. DEC-131.
- Idle labels at their own 400 width (`holdLabelWidth={false}`): with the kit's 500-width hold the toolbar is 2.35 % off SHL-01a. DEC-131.
- Interim Go… replaces the legacy SPEC-302 search palette in the toolbar until P-02 (AC 1.1.8 says no search); `shell/Palette.tsx` and its test stay for P-02. `?` opens the interim Go… (it lists the shortcuts) until SHL-03's dialog (P-01-T08).
- `firmTitle` is the membership's `firm_name` ("Brightwater Hale"); the legal name "Brightwater Hale LLP" arrives with `/v1/me` v2 (P-01-T04).
- `nav aria-label` is the kit's "Modules"; §5.5 says "Primary". The More menu is the kit's 220 w; the spec says 240. Both are F-05-T18's.

## Open gaps
- Support contact and status page addresses are deployment settings (`VITE_SUPPORT_EMAIL`, `VITE_STATUS_PAGE_URL`); unset, the contact line is left out and the link has no target.
