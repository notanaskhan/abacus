# SHL-03 · Firm switcher & profile menu

| Field | Value |
|---|---|
| Route and params | None of its own: local state under the firm pill on every firm route (`legacy/Layout.tsx` mounts `shell/firm/FirmMenu.tsx`; epic §5.1). Artboard: `/components/screens/SHL-03?st=a…f` (gallery builds) |
| Template and host frame | O1 tray (nested tray, white sections) over Home, no scrim · `Wave 0 - Shell.dc.html#shl03` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-03 Firm switcher and profile menu/` · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-01 · P-01-T07 (data), P-01-T08 (this screen), P-01-T11 (auth client), P-01-T16 (Tier C lock, journeys) |
| Manifest status | fixture |

Code: `src/shell/firm/FirmMenu.tsx` (`FirmMenu`, `adminRows`, `cardLine`, `firmFacts`, the profile drawer), `src/shell/firm/copy.ts` (`FIRM_MENU`, `PROFILE`), `src/screens/SHL-03/{index.tsx, scenarios.ts, SHL-03.test.tsx}`; data `src/fixtures/seed/shell.ts`, scenarios `src/fixtures/scenarios/SHL-03.ts`.

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | grace-holloway | Mon Sep 14, 2026 9:24 AM CT | E0 | One staff membership; `nav` firm_settings `write`, users_roles `write`, audit_log `read`; `default_office_id` null | built · fixture |
| b | hannah-leclerc | same | E0 | Every `nav` key `none` → no admin section; `default_office_id` Chicago | built · fixture |
| c | daniel-reyes | same | E0 | `nav` firm_settings `read` (→ "View only"), audit_log `read` | built · fixture |
| d | felix-andersen | same | E0 | `nav` security_center `write`, developer_api `read` (fixture only; `none` in production until G-03), audit_log `read` | built · fixture |
| e | grace-holloway | same | E0 | A second staff membership with `firm.is_sandbox` | built · fixture |
| f | grace-holloway | same | E0 | The office menu open (held in the artboard; in the app → or Enter on the row) | built · fixture |

Loading: the tray opens at once; its rows fill when `/v1/me` and `/v1/me/capabilities` answer, and focus lands on the first row then. Error: a failed capabilities read leaves `nav` empty, so the admin section is hidden (fails closed). Not-allowed: none; every firm user has the tray, and a key reading `none` simply hides its row.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/me` | `MeOut`: `initials`, `job_title`, `default_office_id`, `offices`, `memberships[].firm` (P-01-T04) | `OWN` | — |
| read | `GET /v1/me/capabilities` | `CapabilitiesOut.nav` (five keys), `roles` (firm-wide labels), `office_id` | `OWN` | the admin rows; never a role code (AC 2.1.2) |
| write | `PUT /v1/me/preferences` | `PreferencesIn {default_office_id}` | `OWN` | audited `user_preference.updated` |
| write | `POST /v1/auth/sign-out` | `SignedOutOut {ended}` | `OWN` (bearer) | ends `auth_sessions`, clears the cookie (P-01-T09) |

Switching firm sets the tenant selector (`X-Abacus-Tenant` via `auth/session.chooseTenant`), resets every TanStack Query cache (the active ones, `/v1/me` first, refetch in the new firm) and toasts.

## Copy
Verbatim from spec.md and the canvas's built frames (`shl3Vals`): "Firm", "Your profile", "Default office filter", "All offices", "Notification preferences", "Keyboard shortcuts" with keycaps "⌘ /", "Firm settings", "Users & roles", "Audit log", "Security center", "Developer & API", "View only", "Sign out", "Sandbox · seeded demo data only", the "Sandbox" pill, "Switched to ‹firm›", "Version ‹v›". Undesigned (AC 2.1.5, reviewed by AY): the tray's accessible name "Firm and profile", and the profile drawer "Your profile" with Name, Initials, Role, Job title, Office, Email, Time zone and "Ask your firm admin to change these".

Derived lines: the firm row's "US · Central Time · 46 seats" is `region · zoneName(time_zone) · seats_total seats`; the person card's second line is the firm-wide role labels, the job title and the home office, a label the title already contains left out (DEC-142). The four cards foot to the handoff (test "the person card lines foot to the four handoff cards").

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Firm settings | ADM-01 | `/settings/general` while `firm_settings.v2` is on (G-01-T07; DEC-463); the legacy `/admin/methodology` settings otherwise, until G-01-T17 retires the flag (DEC-113) |
| Users & roles | ADM-02 | planned; legacy `/admin/people` |
| Audit log | ADM-07 | planned; legacy `/admin/audit-log` |
| Security center | ADM-06 | planned; the row only closes the tray |
| Developer & API | ADM-09 | planned; the row only closes the tray |
| Your profile | profile drawer (O2) | built (undesigned) |
| Keyboard shortcuts | shortcuts dialog (C-22 560) | planned; opens the interim Go… frame, which lists the same shortcuts (P-01-T02) |
| Notification preferences | SHL-04 settings menu | opens the notifications drawer |
| Sign out | SHL-06 | the existing sign-in redirect until P-01-T11's auth client |

No ADM screen has a path yet, so there is no `to.ADM0n()` builder; the rows use the legacy paths and move to builders when G-01/G-02 route them.

## Acceptance
- SHL-03 acceptance: tray radius 15 with radius-11 white sections 6 apart, 300 wide, the menu shadow.
- SHL-03 acceptance: Firm settings appears only for the admin, partner and IT frames, from `nav` alone.
- SHL-03 acceptance: the firm pill shows its pressed state while the tray is open.
- SHL-03 acceptance: the person is initials in a chip-coloured 32 circle, never a photo.
- SHL-03 acceptance: the wordmark in the footer (Q4: kept, DEC-142).

## Deviations
- The firm row reads the membership's `firm_name`. The fixture seed's membership carries the short name "Brightwater Hale" (the toolbar pill's), so the fixture row reads "Brightwater Hale" where the handoff reads "Brightwater Hale LLP"; the live seed's firm is named "Brightwater Hale LLP". Open gap: no field carries a separate legal name, so the fixture and the pill cannot both match the handoff.
- The office menu is the kit `Menu` (C-13), which opens below its trigger; the canvas opens it to the right at +12. Tier C will show it.
- The firm row uses `FirmMark`'s initials tile, not the canvas's wave mark (the wave is the demo firm's own drawing).
- The 560 shortcuts dialog and ⌘ / are not built: Keyboard shortcuts opens the interim Go… frame.
- "Version ‹v›" reads `VITE_APP_VERSION` and is hidden when unset (tests and the gallery).
- Parity: Tier C is not run here; P-01-T16 locks it (epic §5.4). Axe on the scenarios is P-01-T16's.

## Figures
"46 seats": the firm's seat count (22 + 14 + 10, `fixtures/shell.foot.test.ts`).
