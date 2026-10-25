# ADM-02 · Users & roles (+ permission matrix)

| Field | Value |
|---|---|
| Route and params | `/settings/people` (G-01 §5.1) behind `firm_settings.v2`. Search params: `segment` (`users` · `templates` · `invitations` · `independence`), `role` (template key), `office` (office id), `team` (team id), `status` (`active` · `invited` · `deactivated`; absent is every status, which Users opens with: DEC-353), `q`, `template` (the highlighted grid column), `ov` (`invite` · `person:<userId>`). Names, emails and TINs never travel in a path. Artboards: `/components/screens/ADM-02?st=a…g` |
| Template and host frame | T12 `SettingsLayout` (F-05-T45; `bare`, `wide` form pane with a centred Segmented in the pane header) with a T1-density people table, `TallyStrip` (C-01), `SearchField` and `FilterChip`s, Tabs Kit `Segmented` + `Count` (C-05), `CategoryList` grammar and the `CapabilityMatrix` grid, O2 480 `Drawer`s, `ConfirmDialog`, `Toast` · `Wave 2 - Intake & Admin.dc.html#adm02` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ADM-02 Users and roles - permission matrix/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21. State g has no artboard (DF-07) |
| Epic and tasks | G-01 · contracts G-01-T01 (TASK-1225) · stub T02, consumer tests T03 · people v2 T05 (TASK-1150, DEC-286) · seed and fixtures T06 (TASK-1151, DEC-287) · screen T10 (TASK-1226) · independent AC tests T11 · annual independence backend T13 · Playwright T16 · parity lock and legacy retirement T17 |
| Manifest status | planned with its path (`routes/manifest/adm.ts`, `/settings/people`): built on fixtures by G-01-T10 behind `firm_settings.v2`, kept `planned` for CLI-02's reason (DEC-195): ADM-01 → ADM-02 is wired in `routes/firm/settings.tsx`, not with `to.ADM02()`, because `to` carries the manifest's names, which the production dist must not hold. a–f live after the staging walk; g live once G-01-T13 answers `GET /v1/firm/independence/annual` |

Code (G-01-T10): `src/routes/firm/settings.tsx` (`/settings/people`), `src/screens/ADM-02/{index.tsx, users.tsx, templates.tsx, drawers.tsx, independence.tsx, model.ts, copy.ts, scenarios.ts, ADM-02.test.tsx}`, `src/fixtures/{handlers/firm-settings.ts, seed/firm-people.ts, scenarios/ADM-02.ts}`, gallery entry in `src/screens/gallery.tsx`. In `packages/ui`: `CapabilityMatrix` (`components/capability-matrix.tsx`), `TallyStrip` pill cards, `PaneHeader` `center`, and `SettingsLayout` `wide`, `headerCenter`, `headerActions` (all additive).

## States

6 artboards in the handoff plus the new state g (DF-07), 7 built here.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | grace-holloway (Grace Holloway, Firm Admin) | Mon Sep 14, 2026, 9:24 AM CT | E0 | `GET /v1/firm/staff`: 46 rows in six bands (7 · 7 · 11 · 14 · 5 · 2), tallies seats 46 of 46, roles 7 · 37 · 2, sign-in 46 of 46, walls 3, seasonal 5 ending Oct 31 | built · fixture (T10); Prod |
| b | grace-holloway | same | E0 | `?segment=templates&template=partner`: `GET /v1/firm/role-templates`, eight templates (7 · 4 · 6 · 8 · 8 · 11 · 1 · 1 = 46), the 16-row grid, the locked Accrued Agent row; Partner column highlighted | built · fixture (T10); Prod |
| c | grace-holloway | same | E0 | `?ov=invite` with seats used = total: the amber banner and Send invite disabled; a direct POST answers `409 seats_full {used, total}` | built · fixture (T10); Prod |
| d | grace-holloway | same | E0 | `?ov=person:<Lena Park>`: `GET /v1/firm/staff/{id}` (template Tax Preparer · seasonal, Denver, access ends Oct 31, 2026, offshore off, one wall, assignments, last three sign-ins) | built · fixture (T10); Prod |
| e | grace-holloway | Mon Nov 2, 2026, 9:24 AM CST | after the access-end job (G-01-T13) | the five seasonal memberships `deactivated` on Oct 31: their rows read "Deactivated Oct 31", tally "41 of 46" | built · fixture (T10); Prod once T13's job runs |
| f | grace-holloway | Mon Jan 5, 2026, 10:12 AM CT | Lena Park's Jan 5 invitation | Lena Park's row is an invitation (`status invited`, expires Jan 19, 2026): "Invite pending · expires Jan 19", Sign-in "—", Last active "—"; Invitations 1; "46 of 46 · 1 pending" | built · fixture (T10); Prod |
| g | margaret-okonkwo (Margaret Okonkwo, Managing Partner) | Mon Sep 14, 2026, 9:24 AM CT | E0 | `?segment=independence`: `GET /v1/firm/independence/annual?year=2026`, each seat holder's status for the year (Confirmed with date · Not yet · Declined with a note), counts that foot to the seat holders; names from `GET /v1/firm/members` | built · fixture (T10); Prod once G-01-T13 replaces the 501 stub |

State g's self-confirm dialog in the SHL-03 profile drawer (AC6.1) is not built in T10: it needs T13's route and the firm's `independence.annual_statement` text, which is firm content (§1.8.4 fallback 2; DEC-353).

Non-artboard states (data conditions, never an `st` prop):

| State | Data condition | Rendering |
|---|---|---|
| Loading | the staff list or role templates pending | `SkeletonRows` in the table body; tallies absent |
| Filtered empty | filters or search match nothing | "No people match these filters." with "Clear filters" |
| Error | the list fails | ViewState error |
| Not allowed | the viewer lacks `firm.read_people` (the overview answers 404 as on ADM-01) | "You don't have access to firm settings." |
| Users not readable | a partner or security admin: `GET /v1/firm/staff` stays on `firm.manage_users` (DEC-286) | the Users and Invitations segments are absent; Role templates (and Independence where `independence.annual_read` holds) remain |
| Step-up | a role change, deactivation or invite answers 403 (stale second factor) | "Confirm it's you to change people" (the T12 step-up slot) |
| Invitations empty | no pending invitation | "No pending invitations." |
| Flag off | `firm_settings.v2` off | "This settings section isn't built yet." |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/firm/staff?q&role_template&office_id&team_id&status&band` | P-36 envelope: `items` (StaffRowV2Out), `total`, `counts` per band (over the filters, less the band), firm-wide `tallies` | `firm.manage_users` (fresh MFA; DEC-286 keeps it there until the SPEC-024 tests move) | firm admin; each row's `allowed_actions` carries `firm.manage_users`, `security_role.assign` |
| read | `GET /v1/firm/staff/{user_id}` | row, firm role, `security_admin`, `wall_ids`, `assignment_count`, last three sign-ins (method, MFA; no IP is stored live), `annual_independence`, `version` | `firm.read_people` | firm admin, security admin, partners |
| read | `GET /v1/firm/role-templates` | templates with `member_count`; grid rows (key, actions, cells `allow · conditional · delegated · deny · locked`, conditions, `source`), the locked `accrued_agent` row | `firm.read_people` | same |
| read | `GET /v1/firm/offices` · `GET /v1/firm/teams` | office and team names for cells and filters | `org_structure.read` | firm staff |
| read | `GET /v1/walls` | wall register (user, client, created) for the "Wall n" tags and the drawer's walls | `wall.list` (fresh MFA) | firm admin, security admin, partners; on 403 the tags are simply absent (DEC-43: never a count) |
| read | `GET /v1/clients/{client_id}` | the walled client's name in the drawer | `client.read` | the viewer's own visibility |
| read | `GET /v1/firm/members` | names for state g | `wall.create` | firm admin, partners |
| read | `GET /v1/firm/independence/annual?year=` | rows (user, status, decided_at, note), `counts` | `independence.annual_read` | firm admin, quality partner, partners; 501 until G-01-T13 |
| write | `POST /v1/firm/staff/invitations` | template, level, office, team, seasonal end, offshore, display name; `409 seats_full · already_member`; `422 access_ends_required` | `firm.manage_users` | firm admin |
| write | `PUT /v1/firm/staff/{user_id}/role` | `{role_template, level}`; `409 last_admin` | `firm.manage_users` (fresh MFA) | firm admin; audited "Role changed by Grace Holloway" |
| write | `POST /v1/firm/staff/{user_id}/deactivate` | `{reason: manual}`; `409 last_admin` | `firm.manage_users` (fresh MFA) | firm admin |

Every control renders from `allowed_actions` and `useCan`, never a role comparison (AC11.1).

## Status
- `membership` (`status-vocabulary.yaml`, G-01 §3.3–3.4): `active` · `invited` "Invite pending" (amber) · `deactivated` "Deactivated" (muted).
- `invitation` row words (DF-31): `invited` "Invite pending · expires {date}" (amber) · `deactivated` "Deactivated {date}" (tag).
- `annual_independence` (G-01 §3.6): `confirmed` "Confirmed" (green-tint) · `not_yet` "Not yet" (muted) · `declined` "Declined" (red-tint).
- Tally pills: SEATS "Full" (amber) when used ≥ total; SIGN-IN green solid with a check.

## Copy
Copy keys live in `screens/ADM-02/copy.ts`; strings verbatim from spec.md and the screenshots.

| Key | String |
|---|---|
| `title` | "People" |
| `segments` | "Users" · "Role templates" · "Invitations" · "Independence" (g; DF-07) |
| `addSeats` · `invite` | "Add seats…" (planned until G-04) · "Invite user…" |
| `tally` | "SEATS" "{used} of {total}" (f: "46 of 46 · 1 pending") + "Full" · "ROLES" "{p} partners · {n} professionals · {o} operations" · "SIGN-IN" "SSO + MFA {n} of {of}" · "WALLS" "{n} active" · "SEASONAL" "{n} · access ends {date}" |
| `search` | "Search people" |
| `chips` | "Role │ All" · "Office │ All offices" · "Team │ All" · "Status │ All" (a's canvas reads "Active": DEC-353) |
| `count` | "{n} people" |
| `columns` | "Name" · "Role" · "Office" · "Team · groups" · "Sign-in" · "Last active" |
| `bands` | "PARTNERS" · "MANAGERS & REVIEWERS" · "SENIORS" · "STAFF & PREPARERS" · "SEASONAL" · "OPERATIONS" |
| `wallTag` | "Wall {n}" |
| `templates` | "Partner" "Sign-off L4, release, final approval" · "Manager" "Review L2/L3, AJE within threshold" · "Tax Reviewer" "Review returns, export after approval" · "Senior" "Prepare, first-level review" · "Staff" "Prepare and adopt agent work" · "Tax Preparer" "Prepare returns" · "Firm Admin" "People, clients, firm-ops agents" · "IT / Security" "Security roles, SSO, keys, audit log" |
| `agent` | "Accrued Agent" · "non-human · locked" · "Accrued Agent — Draft · Test · Propose · Chase within the invoking user's scope. Never approves, signs off, releases, sends final, posts or exports." |
| `grid` | "Capability" · row labels from `role-templates.yaml` · footer "Default policy from 01 §2.4. Firms may only make it stricter. Hard limits are locked." |
| `cells` (text alternatives) | "Allowed" · "Allowed: {condition}" · "Allowed with a condition: {condition}" · "Draft or propose only" · "No access" · "Locked" |
| `invite` drawer | "Invite user" · "Person" · "Name" "First and last name" · "Email" "name@example.com" (the canvas writes the firm's domain, firm content that never ships in code: DEC-353) · "Access" · "Role" · "Office" · "Team" · "Seasonal" · "Access ends" · "Offshore / restricted" · helper (DEC-352) · banner "All {total} seats are assigned. Add seats or deactivate a user first." · "Cancel" · "Send invite" |
| `person` drawer | "Access" · "Role" "{template}" / "{template} · seasonal" · "Office" · "Team" · "Email" · "Access ends" · "Offshore / restricted" · "Status" · "Ethical walls" "{client} (added {when})" · "Assignments" · "Sign-in history" "{when} · {method} · MFA[ · {ip}]" · "Change role…" · "Deactivate…" |
| `confirm` | "Change {name}'s role to {template}?" · "Deactivate {name}?" |
| `independence` | "Independence · {year}" · "Confirmed {date}" · "Not yet" · "Declined" · "{confirmed} confirmed · {notYet} not yet · {declined} declined" |

Row text (names, emails, titles, offices, teams, groups) is seed data, never `copy.ts`.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| A row (its name is the button) | the person drawer (`?ov=person:<userId>`); role changes from its "Change role…" menu with a confirm | in-screen |
| "Wall n" tag; the drawer's wall line | ADM-03 walls (`/settings/offices#walls`) | planned (G-01-T14); plain text until then |
| "Invite user…" | the invite drawer (`?ov=invite`) | in-screen |
| "Add seats…" | ADM-14 plan dialog | planned (G-04); hidden in production |
| Role change | ADM-07 "Role changed by Grace Holloway" | planned (G-02) |
| Section list | ADM-01 and the other sections | ADM-01 built; others planned |
| A person (later) | CLI-08 independence drawer | planned (P-07) |

Inbound: ADM-01 (People section and At a glance), SHL-03 "Users & roles", ADM-03 seat counts and team chips (`?office=`, `?team=`).

## Acceptance
- ADM-02 acceptance: exactly 46 rows: the 14 named staff and the 32 §9.2 generator names, with offices Chicago 22 · Denver 14 · New York 10.
- ADM-02 acceptance: role template counts 7 + 4 + 6 + 8 + 8 + 11 + 1 + 1 = 46; team counts 16 + 21 + 7 + 2 = 46.
- ADM-02 acceptance: the 16 capability rows match 01 §2.4 symbol for symbol (including "● after approval" for Tax Reviewer export, "● EP only" for release, D for draft-only); the Accrued Agent row is locked and never approves.
- ADM-02 acceptance: no invented people: the pending-invite state reuses Lena Park (Jan 5, 2026), not a 47th name.
- ADM-02 acceptance: table density matches T1 (th 30, rows 44, hairlines, no zebra); the drawer grammar matches the fieldset cards.
- ADM-02 acceptance: the seat counter "46 of 46" and the blocked invite agree with ADM-01.
- ADM-02 acceptance: wall tags appear only on VH, LP and PS, matching ADM-03.
- G-01 AC5.4: selecting Partner highlights its column; hovering or focusing a ◐ shows its condition.
- G-01 AC6.3: the independence section's counts foot to the seat holders.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Bands (a) | 7 + 7 + 11 + 14 + 5 + 2 = 46 | `fixtures/firm-people.foot.test.ts`; `ADM-02.test.tsx` (a) |
| Offices (a) | 22 + 14 + 10 = 46 | same |
| Templates (b) | 7 + 4 + 6 + 8 + 8 + 11 + 1 + 1 = 46 | same; `ADM-02.test.tsx` (b) |
| Teams | 16 + 21 + 7 + 2 = 46 | `firm-people.foot.test.ts` |
| Roles tally | 7 partners + 37 professionals + 2 operations = 46 | same |
| After season (e) | 46 − 5 = 41 of 46 | `ADM-02.test.tsx` (e) |
| Pending (f) | 45 active + 1 pending = 46 of 46 · 1 pending | `ADM-02.test.tsx` (f) |
| Independence (g) | confirmed + not yet + declined = 46 | `ADM-02.test.tsx` (g) |

## AVOID
Gradients in product UI, emoji, saturated blue SaaS defaults, heavy shadows, invented colours, lorem ipsum, photo avatars, coloured initials, invented people (only the 14 named staff and the 32 generator names), checkbox grids that let a firm grant the agent approval rights, zebra rows.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DEC-35 / DF-24 | f reads "Invite pending · expires Jan 19" (14 days), not "expires Jan 12" | 14-day invitations | DEC-35; parity masks the expiry string |
| G-B06 | e renders on Mon Nov 2, 2026 (the label date), not the README's rendered date | the README's rendered date is wrong | G-01 §2.1 |
| DEC-352 | The invite drawer's offshore helper reads "Members are assigned only to clients with a valid §7216 offshore consent; SSNs masked." instead of "Members see only clients with a valid §7216 offshore consent; SSNs masked." | Offshore is not a wall (TASK-1207, DEC-319): offshore members see what their roles reach; consent gates assignment and reveals stay refused | DEC-352; parity masks the helper |
| DF-07 | State g (Independence segment) has no artboard: a fourth segment with the T1 table grammar (person, office, status pill, decided date, note) and a counts line | DEC-91 places the annual confirmation here; DF-07 is AY's design call | DEC-352 |
| DEC-353 | The SHL-03 self-confirm dialog (AC6.1) waits for G-01-T13 | `POST /v1/me/independence/annual` is a 501 stub and the statements are firm content (`independence.annual_statement`) not yet registered | DEC-353 (§1.8.4 fallback 2) |
| DEC-286 | Partners and security admins don't see Users or Invitations | the list stays on `firm.manage_users` | DEC-286 |
| DEC-353 | Sign-in cells read "SSO ✓", not "Microsoft SSO ✓" | the list row carries no identity-provider name; the firm's provider is G-02's security setting | DEC-353; parity masks the cell text |
| DEC-353 | Daniel Reyes's 6px online dot is not drawn | no presence fact is served | DEC-353 |
| DEC-353 | The drawer's Assignments reads "{n} assignments" | the person read carries `assignment_count`, not the engagements; names wait for `register_active_engagements` to return rows | DEC-353 |
| DEC-353 | The grid draws no lock beside hard-limit rows or their "—" cells; AJE's "● / ●" pair reads as one cell with its condition | `role-templates.yaml` declares no hard-limit flag and one cell per template | DEC-353; a yaml and codegen change (protected) |
| DEC-353 | Role templates list rows carry the descriptions drawn on the canvas (not in spec.md) | the screenshots are the built screen | DEC-353 |
| DEC-353 | Users opens with "Status │ All", not "Status │ Active" | e and f open on deactivated and invited rows; one default for every state | DEC-353; parity masks a's chip |
| DEC-353 | g's table has no Office column | a partner can't read the people list (DEC-286), and the year's rows carry ids only | DEC-353 |
| DEC-353 | A role changes from the person drawer's "Change role…" menu (confirm, then fresh MFA), not from a menu on the Role cell; the row's ··· is drawn but the row itself opens the drawer | one place for a person's writes | DEC-353 |
| DEC-353 | The invite drawer opens with Tax Preparer and the HQ office, and no team chosen (the canvas shows Tax) | a default team is a guess; the person picks it | DEC-353 |
| — | "Add seats…" is hidden in production | G-04 owns the seat purchase | G-01 §2.1 |
| — | The role template editor is not built; the grid is read-only | OQ-4 | G-01 §2.2 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a–e | C (locked in G-01-T17) | not run (fixture build; axe in `e2e/screens/adm-02.spec.ts`, G-01-T16) | mask the Sign-in cells and the section list (DEC-288) |
| f | C | not run | mask the expiry string (DEC-35) |
| g | — | — | no reference PNG (DF-07); covered by interaction tests |
| host | D | — | pane header 46, tally cards 52, th 30, rows 44, group band 24, drawer 480 |

## Open gaps
- The f snapshot carries no last-active times (the fixture holds E0's times only), so every Last active reads "—" on Jan 5; the canvas shows Jan dates for the others. Fixture-only.
- The "Wall n" tag counts the walls the register lists for that person; with a stale second factor the register answers 403 and no tag shows (never a count; DEC-43).
- Sign-in history shows the IP only when served: none is stored live (DEC-286), so production reads "{when} · {method} · MFA"; the fixture serves the canvas's IP.
