# ADM-01 · Settings home & firm profile

| Field | Value |
|---|---|
| Route and params | `/settings/general` (G-01 §5.1) behind `firm_settings.v2`; `?ov=add-seats` (fixture only, the plan dialog until G-04). A section row or an At a glance row opens `/settings/<section>`; leaving a dirty form asks first. Artboards: `/components/screens/ADM-01?st=a…f` |
| Template and host frame | T12 `SettingsLayout` (F-05-T45; `bare` inside the app shell, `aside` for the 330 At a glance column, DEC-288) · `Wave 1 - Workbench & Ops.dc.html#adm01` (the production TPL-12 specimen) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ADM-01 Settings home - firm profile/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | G-01 · contracts G-01-T01 (TASK-1225) · family stub G-01-T02, consumer tests T03 · settings registry T04 · seed and fixtures T06 (TASK-1151) · screen T07 (TASK-1152) · independent AC tests T11 · Playwright T16 · parity lock and legacy retirement T17 |
| Manifest status | fixture (`routes/manifest/adm.ts`, path `/settings/general`); live behind `firm_settings.v2` once walked on staging |

Code (G-01-T07): `src/routes/firm/settings.tsx`, `src/screens/ADM-01/{index.tsx, copy.ts, scenarios.ts, ADM-01.test.tsx}`, `src/fixtures/{handlers/firm-settings.ts, seed/firm-people.ts, scenarios/ADM-01.ts, firm-people.foot.test.ts}`, gallery entry in `src/screens/gallery.tsx`.

## States

6 artboards in the handoff, 6 built here.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | grace-holloway (Grace Holloway, Firm Admin) | Mon Sep 14, 2026, 9:24 AM CT | E0 | Every section answers with `allowed_actions: [firm.manage_settings]`; nothing edited: Save disabled | built · fixture (T07); live once T04's keys and T08's offices answer on staging |
| b | grace-holloway | same | E0 | a, then Default time zone CT → "Eastern Time (ET)": "Unsaved changes", Save enabled | built · fixture (T07) |
| c | grace-holloway | same | E0 | a, then Display name emptied: "Required" in red-ink with the helper; Save blocked (server also answers `422 display_name_required`) | built · fixture (T07) |
| d | daniel-reyes (Daniel Reyes, Partner) | same | E0 | Sections answer `read_only_reason: firm_admin_only` and no write action: amber banner, locks, no Save; At a glance stays | built · fixture (T07) |
| e | felix-andersen (Felix Andersen, IT / Security, `security_admin`) | same | E0 | As d, and the overview marks `plan` not visible (its section answers 404): no Plan & seats; Security first in At a glance | built · fixture (T07) |
| f | grace-holloway | same | E0 | b saved: `PATCH /v1/firm/settings/profile` with the version read; toast "Firm settings saved" | built · fixture (T07) |

Non-artboard states (data conditions, never an `st` prop):

| State | Data condition | Rendering |
|---|---|---|
| Loading | overview or a section pending | fieldsets absent until they answer; the read-only banner never flashes for a firm admin (DEC-288) |
| Not allowed | `GET /v1/firm/settings/overview` answers 404 (no settings role; AC1.8, ADR-024) | "You don't have access to firm settings." |
| Step-up | a save answers 403 (stale second factor) | T12's step-up slot: "Confirm it's you to save firm settings" (F-05 R10, DEC-288) |
| Stale version | a save answers `409 stale_version` | toast "Changed by someone else — reload" (AC1.4) |
| Provider unavailable | an At a glance provider times out (500 ms) | that row reads "Status unavailable" with no disc (AC2.3) |
| Flag off | `firm_settings.v2` off | "This settings section isn't built yet." |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/firm/settings/overview` | sections (key, group, visible), At a glance rows (key, tone, facts, href, unavailable), `firm_name`, `as_of` | `firm.read_settings` | firm admin, practice leader, security admin, level partner; everyone else 404 |
| read | `GET /v1/firm/settings/{section}` (`profile`, `defaults`, `plan`) | registered keys with `value` and `editable`, `version`, `read_only_reason`, `allowed_actions` | `firm.read_settings` | `plan` absent for `security_admin` (AC1.7); `read_only_reason: firm_admin_only` for partners and security admins |
| write | `PATCH /v1/firm/settings/{section}` | `{version, values}`; `422 display_name_required · unknown_setting`; `409 stale_version` | `firm.manage_settings` (fresh MFA) | firm admin only |
| read | `GET /v1/firm/offices` | offices with seats and registered facts (returns) | `org_structure.read` | fieldset B renders only when it answers |
| read | `GET /v1/firm/members` | person picker for Billing contact | `wall.create` | firm admin, partners |

## Status
At a glance discs (`StatusDisc`): `ok` olive ✓ · `attention` amber triangle · `partial` half disc. No status-vocabulary object; the tones are the overview's.

## Copy
Copy keys live in `screens/ADM-01/copy.ts`; strings verbatim from spec.md. Key strings: "Firm settings" · "Settings" · "Only firm admins can edit these settings." · "Firm settings saved" · "Unsaved changes" · "Discard changes?" · "Required" · "Enter the name clients see in the portal." · "Fixed at provisioning. Client data, logs and AI inference stay in the US." · "All seats are assigned. Add seats before inviting another user." · "{used} of {total} used" · "{partners} partners · {professionals} professional staff · {operations} operations; {seatless} back-office staff hold no seat" · "All offices" · "{seats} seats · {returns} returns" · "At a glance" · "Updated {time}" · the eleven At a glance lines (`GLANCE` in copy.ts) · "Confirm it's you to save firm settings" (G-01 decision, F-05 R10).

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Section row "People"; At a glance People | ADM-02 `/settings/people` | built by G-01-T10 (fixture) |
| Section row "Offices & teams"; At a glance Offices & teams; an office row | ADM-03 `/settings/offices` (`?expand=<code>`) | planned (G-01-T14) |
| Security · AI policy · Consents · Developer · Integrations · Portal · Quality · Monitoring · Audit log | ADM-06 · ADM-04 · ADM-05 · ADM-09 · ADM-08 · ADM-10 · ADM-11 · ADM-12 · ADM-07 | planned (G-02, T-01, R-01, Q-05); "not built yet" in dev and fixture builds, hidden in production |
| "Add seats" helper | ADM-14 plan dialog (`?ov=add-seats`) | fixture only until G-04 |
| "‹ Back" | the previous screen | live |

Inbound: SHL-03 "Firm settings", SHL-06 first sign-in after provisioning (PLT-01).

## Acceptance
- ADM-01 acceptance: fieldset bands (33px), value rows (34px), olive toggle and the mini "+ Office" pill match the Edit Agent sheet grammar.
- ADM-01 acceptance: seats 22 + 14 + 10 = 46; returns 98 + 64 + 62 = 224; "46 of 46 used"; 7 + 37 + 8 = 52 people with 6 seatless back-office staff.
- ADM-01 acceptance: values are TPL-12's, in the same order; only the At a glance card is new.
- ADM-01 acceptance: every At a glance count matches the screen it links to (ADM-02 46 of 46, ADM-03 3 walls, ADM-05 2 expiring + 1 expired, ADM-06 day 4 of 30, ADM-10 6 of 6 templates with 1 draft change, ADM-11 2 at risk + 5 findings, ADM-12 3/1/2).
- ADM-01 acceptance: the section list has its sections in four groups, and no toolbar nav item is active.
- ADM-01 acceptance: the read-only variant shows values but no Save.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Offices | 22 + 14 + 10 = 46 seats; 98 + 64 + 62 = 224 returns | `fixtures/firm-people.foot.test.ts`; `ADM-01.test.tsx` (a) |
| People | 7 + 37 + 8 = 52; 6 seatless | same |
| Seats | 46 of 46 used = ADM-02a's tally | same |

## AVOID
Gradients in product UI, emoji, saturated blue toggles or links, heavy shadows, invented colours, lorem ipsum, boxed or native inputs, centred labels, a left global sidebar, the words Accrual/Arc/ACME, any Accrued logo in the firm chrome.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DEC-288 | The section list is the fourteen sections of G-01 §2.1 in four groups (FIRM · SECURITY & AI · CLIENTS · QUALITY), not the canvas's eight; unbuilt sections are planned (hidden in production) | One section list for every ADM screen | DEC-288 |
| DEC-288 | The People line reads "…; 6 back-office staff hold no seat" computed from the People glance row's facts | Never typed | DEC-288 |
| — | At a glance in production shows only rows whose owners registered a provider (People, Offices & teams); fixture mode shows all eleven for parity | AC2.1, AC2.2 | G-01 §3.2 |
| — | "Add seats" helper and "Replace…" logo are planned controls (hidden in production) | G-04 owns seats purchase; logo upload is P-08's | G-01 §2.2 |
| DEC-352 | The step-up copy "Confirm it's you to save firm settings" has no handoff artboard | F-05 R10: G-01 decides the T12 slot's words | DEC-352 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a–f | C (locked in G-01-T17) | not run (fixture build; axe in `e2e/screens/adm-01.spec.ts`, G-01-T16) | the section list differs by design (DEC-288): masked |
| host | D | — | subbar 42, pane header 46 at 14.5/500, band 33, value row 34, toggle 38×22 |

## Open gaps
- Offices (fieldset B) render only when `GET /v1/firm/offices` answers; returns per office are T-02's office facts (fixture until then).
- Return approval policy, AJE thresholds, auto mode, modules and renewal are later epics' keys; they render only when the section answers them (fixture-only now, AC2.2 parity).
