# SHL-05 · Support panel

| Field | Value |
|---|---|
| Route and params | `?ov=support` over any firm screen (tabs `chat`, `help`, `help:<slug>`, `status`) |
| Template and host frame | O2 right drawer 480 × 840 (geometry identical to SHL-04) |
| Surface | firm (never mounted in the portal, INV-4) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-05 Support panel/` (no `revision.md`) |
| Epic and tasks | G-04 · SPEC-680 AC-44 to AC-56, SPEC-681 AC-18 to AC-20 · G-04-T06 (contract), T03 (stub and typed fixtures), T10 (API), T13 (scenarios), T19 (screen), T21 (parity) |
| Persona | Grace Holloway (Firm Admin); Felix Andersen on c |
| Flags | `support.panel_v2` (off: the Support pill opens P-01's interim frame) |
| Priority | P2 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

7 artboards, all built.

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Chat · online | chip "Online · replies in ~4 min" (7-day median, ≥ 5 samples); session notice card; Grace's and Ines's bubbles; Related article "Exporting a return to CCH Axcess: statuses and retries" (4 min read); inline request card "2025 Form 1040 · Jonah & Claire Feld" · 2 hours · amber "Awaiting firm approval" with Decline and Review in Settings | Mon Sep 14, 2026, 9:24 AM CT | Aug 17 + Sep 14 support history | D · **C locked** | planned · `shl05.a` |
| b | Offline | "Offline · we reply by 8:00 AM CT"; composer "Leave a message"; "We'll email grace.holloway@brightwaterhale.com when we reply." | outside support hours | E0 | D · **C locked** | planned · `shl05.b` |
| c | Session granted · Felix | green-tint "Granted by Felix Andersen · until 11:41 AM" + Revoke | Mon Sep 14, 2026, 9:41 AM CT | E0 | D · **C locked** | planned · `shl05.c` |
| d | Help articles | search; groups Suggested for this page (context TPL-01), Tax returns, Agents & approvals, Client portal; six article rows | Mon Sep 14, 2026, 9:24 AM CT | E0 content | D · **C locked** | planned · `shl05.d` |
| d′ | Article open | the article in the drawer with a back chevron; structured blocks only | Mon Sep 14, 2026, 9:24 AM CT | E0 content | D · **C locked** | planned · `shl05.d2` |
| e | System status | seven rows; CCH Axcess Tax export amber "Needs attention" · "Delays up to 15 min since 8:40 AM CT"; "Your firm's data region: US"; Incident history | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · **C locked** | planned · `shl05.e` |
| f | Empty chat | two suggestion cards "Ask about a sync", "Report a problem with an agent run" | Mon Sep 14, 2026, 9:24 AM CT | new user | D · **C locked** | planned · `shl05.f` |
| declined | — | "Declined by Grace Holloway" on the card | — | — | D | planned |
| ended | — | session ended, expired or revoked: the card's terminal word | — | — | D | planned |
| cannot approve | — | a viewer neither firm admin nor IT/Security: card read-only "Waiting for Firm Admin or IT/Security" | — | — | D | planned |
| no results | — | help search with no results | — | — | D | planned |
| status unavailable | — | the status read failed: designed error | — | — | D | planned |
| flag off | — | `support.panel_v2` off: P-01's interim frame | — | — | — | planned |

Fixture scenarios: `apps/web/src/fixtures/scenarios/support.ts` (G-04-T13) from the typed fixtures (components, help groups, suggestions in `platform/g04_fixtures.py`); thread text is the handoff's, held as seed content for Brightwater Hale. Copy keys `shl05.<state>.<element>`; help articles, support hours and status components are database content (T20), never `copy.ts`.

## API

`docs/contracts/support.md`: `GET /v1/support/conversation`, `POST …/messages`, `GET /v1/help/articles?context=&q=`, `GET /v1/help/articles/{slug}`, `GET /v1/status`; `GET /v1/support-sessions`, `POST …/{id}/decline` and `…/revoke` (SPEC-681). Actions `support.chat` (OWN), `help.read`, `status.read`, `support_session.*`.

## Links

| From | To | Status |
|---|---|---|
| Review in Settings | ADM-06 `/settings/security#support-access` | live |
| Status rows, Incident history | the external status page (new tab) | live |
| Article screen links | the named screen | planned (T19) |

## Notes

Support is a named human ("Ines at Accrued Support"); no chatbot avatar or mascot. Messages are plain text rendered without HTML or auto-links; the drawer is `role=dialog` with `aria-modal`, focus to ✕ and back to the Support pill; Escape closes it.

## Deviations

| ID | Deviation | Decision | Owner |
|---|---|---|---|
| DV-1 | The composer's paperclip is omitted: a file sent to support is content disclosure outside a session (ADR-028, DEC-72) | DEC-5206 | ayushkbhatia |
| DV-2 | The inline card's scope line is resolved in the firm's context (SPEC-681 AC-18); until `engagements` registers its labeler the card reads the generic scope ("Content · 1 work item") | DEC-5205 | notanaskhan (T10) |

## Acceptance

SPEC-680 AC-44 to AC-56 and SPEC-681 AC-18 to AC-20 for this screen; each becomes a test named "SHL-05 acceptance: <criterion>". Design-fidelity sign-off: Ayush.
