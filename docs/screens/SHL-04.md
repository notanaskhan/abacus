# SHL-04 · Notifications panel

| Field | Value |
|---|---|
| Route and params | `?ov=notifications` on any firm route (the `notifications` drawer layer, `app-core/overlays.ts` registry). The bell toggles it; Back closes it. Artboard: `/components/screens/SHL-04?st=a…g` (gallery builds) |
| Template and host frame | O2 drawer, peek (480, no scrim, the page stays live) · `Wave 0 - Shell.dc.html#shl04` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-04 Notifications panel/` (spec.md, revision.md R2) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-01 · P-01-T07 (data), P-01-T10 (frame, tabs, day groups; this contract), P-01-T13 (Undo route), P-01-T16 (Tier C lock, journeys) |
| Manifest status | planned. The drawer is built on fixtures, but the manifest stays planned until the SHL-04 → SHL-03 link and the inline approval land (see Deviations) |

Code: `src/shell/firm/NotificationsDrawer.tsx` (`NotificationsDrawer`, `groupByDay`, `tabOptions`, `rowButton`, the overlay registration), `src/shell/notifications.ts` (`firmDayGroup`, `kindGlyph`, `feedHref`), `src/shell/firm/copy.ts` (`NOTIFICATIONS`), `src/screens/SHL-04/{index.tsx, scenarios.ts, SHL-04.test.tsx}`; data `src/fixtures/seed/notifications.ts`, scenarios `src/fixtures/scenarios/SHL-04.ts`.

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc | Mon Sep 14, 2026 9:41 AM CT | E0 | Rows a–i, 4 unread; counts approvals 3, mentions 1 | built · fixture |
| b | hannah-leclerc | same | E0 | Approvals tab: the rows with `pending` (a, b, d) | built · fixture |
| b′ (`bp`) | hannah-leclerc | same | E0 | Approvals tab, nothing pending → EmptyState | built · fixture |
| b_raj | raj-malhotra | same | E0 | Approvals adds the Copperleaf `proposal_routed` row (agent, deep link only) | built · fixture |
| c | hannah-leclerc | same | E0 | Row d decided: `facts.receipt`, no `inline_actions`, not pending | built · fixture (receipt line; the Accept and Undo controls are deferred) |
| d | hannah-leclerc | same | E0 | Every row read → no dots; Mark all read has nothing to do | built · fixture |
| e | hannah-leclerc | same | E0 | No rows → "You're all caught up." | built · fixture |
| f | hannah-leclerc | same | E0 | The feed never answers → 5 skeleton rows, `aria-busy` | built · fixture |
| g | hannah-leclerc | Thu Oct 1, 2026 11:00 AM CT | E2 | The R2 kinds: a to-do, a template update, two trigger runs | built · fixture |
| settings | hannah-leclerc | Thu Oct 1 11:00 AM CT | E2 | The Notification settings menu | deferred (scenario data exists) |

Error: a failed feed shows an error EmptyState with Retry. Not-allowed: none; every firm user has their own feed.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/notifications/feed?tab=&limit=30&days=30` | `NotificationFeedOut {items, next_cursor, counts, unread_count}` (C16 v2 at `/feed` during the overlap) | `OWN` | the All page always loads for the counts; the shown tab loads its rows |
| write | `POST /v1/notifications/{id}/read` | — | `OWN` | when a row is opened, never when the drawer opens |
| write | `POST /v1/notifications/read-all` | `ReadAllOut` | `OWN` | Mark all read; the bell's v1 `unread_count` is refetched |

## Copy
Verbatim from spec.md and revision.md: "Notifications", "Mark all read", "All", "Approvals", "Mentions", "Client activity", "Today", "Open approvals queue →", "No approvals waiting on you." / "Decisions, sign-offs and agent proposals that need you appear here.", "You're all caught up." / "Approvals, mentions, client uploads and finished runs appear here.", "Showing 30 days". A row's title, context, pill, receipt and deep-link button come from its read-time `facts` (`title`, `context`, `pill`, `receipt`, `button`) until the kind templates exist; a row without a title falls back to the v1 kind text. Undesigned: the tab track's accessible name "Notification kinds" and the visually hidden "Unread". The load error reuses SPEC-305's "Couldn't load notifications".

Day groups use the firm's calendar (`/v1/me/capabilities.tz`): "Today", then each earlier day by weekday and date ("Friday, September 11"), from `firmDayGroup(iso, now, tz)` with `now` from the app clock (`app-core/clock.useNow`). SPEC-305's `dayGroup` buckets ("Yesterday", "Earlier this week", "Older") stay for the v1 drawer; the handoff names the day instead.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Rows a–i, g's rows | AUD-07, SHL-12, AUD-06, AUD-03, WB-01, HOME-03, SHL-17, ENG-11, SHL-20, SHL-13 | planned; meanwhile a row with an engagement goes to its legacy page (`/engagements/$id`, `/requests` for client uploads), and one without only marks itself read |
| Open approvals queue → | HOME-02 | planned until I-01; closes the drawer |
| Notification settings | SHL-04 settings menu (R2; the original spec's SHL-03 profile link) | deferred |

## Acceptance
- SHL-04 acceptance: 480 wide, 10 px inset, shell body with white grouped cards, the 46 header with a centred title (O2 `Drawer`, `width={480}`, `peek`).
- SHL-04 acceptance: agent proposals and decisions only deep-link; agent rows' context renders through AgentText and no agent row carries Approve, Sign off, Release, Send, Post or Decide.
- SHL-04 acceptance: unread is weight 500, a 7 px brick dot and a hidden "Unread" label, never colour alone.
- SHL-04 acceptance: the bell dot follows `unread_count` after Mark all read.
- SHL-04 acceptance (R2): frame g shows one row of each new kind, the trigger rows begin "Auto-started by trigger ·", and nothing applies a template from the drawer.

## Deviations
- **Deferred to a follow-up of P-01-T10:** inline Accept and Return… on row d (`accept_document`, `return_document`), the receipt's 10 s Undo (the undo route is P-01-T13, not in the generated client yet), the Return reason dialog, and the Notification settings menu with its preferences PUT. Frame c shows the receipt from the facts, without Undo.
- The manifest keeps SHL-04 `planned`. With SHL-03 at `fixture`, link-contract rule 1 would require `to.SHL03()` in this folder, but neither overlay has a path, so there is no builder. The R2 revision replaced that link with the settings menu.
- Row i's Timer glyph is not in the icon registry (F-05-T13); `clock` stands in.
- The tabs are the kit `Segmented` (a tablist, 28 high); the spec's track is 26 high and the epic's a11y note asks for a radiogroup. The count is in each tab's text ("Approvals3"), not "Approvals, 3".
- Parity: Tier C is not run here; P-01-T16 locks it. Axe on the scenarios is P-01-T16's.

## Figures
Times tie to TPL-02 (TB complete 9:26, Keystone 8:47, Harborline 8:52; $16,812,400.00; Oct 9 and Oct 15): `fixtures/notifications.foot.test.ts` (P-01-T07). The tab counts 3 and 1 are the server's `counts`.
