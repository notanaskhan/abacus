# CLI-04 · Contacts & portal access

| Field | Value |
|---|---|
| Route and params | `/clients/$clientId/contacts` (CLI-02's "Contacts & access" tab; P-07 §5). Artboards: `/components/screens/CLI-04?st=a…g` |
| Template and host frame | T1 `IndexList` inside the CLI-02 record (subbar + tabs) with the O3 invite sheet, the O2 contact drawer and a 400 Dialog · `Wave 2 - Home & Records.dc.html#cli04` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLI-04 Contacts and portal access/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-07 · contract P-07-T23 · stub P-07-T17 · consumer suite P-07-T18 · live P-07-T25 · AC suite P-07-T26 · screen P-07-T33 |
| Manifest status | planned (`routes/manifest/cli.ts`, `path: null`) until P-07-T33 |

Code to come (P-07 §5): `src/screens/CLI-04/{index.tsx, scenarios.ts, copy.ts, CLI-04.test.tsx}`, `src/fixtures/handlers/contacts.ts`. Flag `contacts.v2`. API: `docs/contracts/contacts-access.md`.

## States

7 artboards (a–g from spec.md); all live once P-07-T25 and T33 merge.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | grace-holloway (Grace Holloway, Firm Admin) | Mon Sep 14, 2026, 9:24 AM CT | E0 | Northwind Robotics, Inc.: six contacts; 3 active · 1 invited · 2 not invited; delegated 10 + 9 + 2 + 2 + 1 = 24, PBC received 11 of 24 | built · live (T33) |
| b | grace-holloway | same | E0 | Harborline Trust Company row's "Invite…": the O3 sheet prefilled with its two delegated requests, MFA locked on by firm policy, link expires 14 days, email preview from the firm's database Invitation template | built · live (T33) |
| c | grace-holloway | same | E0 + the b send | Harborline `invited`, "Sent Sep 14"; toast | built · live (T33) |
| d | grace-holloway (see Deviations) | same | E0 + lock | Sam Ortiz's portal user locked after 3 incorrect codes (P-08): "Locked" + "3 incorrect codes · 9:02 AM", row action "Unlock…" | built · live (T33) |
| e | grace-holloway (see Deviations) | same | E0 | Sam Ortiz "Change scope…": the same sheet titled "Change access — Sam Ortiz" with his 9 delegated requests | built · live (T33) |
| f | grace-holloway | same | E0 | Summit Plan Administrators "Revoke…": Dialog 400; on confirm its grants are revoked and the requests stay with Northwind | built · live (T33) |
| g | grace-holloway | same | E0 | Copperleaf Coffee Roasters, Inc. (non-attest): Tess Moreno owner, Ben Ashby controller and approver of record, "Non-attest client: no SKE designation required" | built · live (T33) |

Loading: the ViewState skeleton. Empty: "No contacts yet." with "+ Invite…". Not-allowed: a walled or unknown client answers 404 and renders not-found (INV-3, DEC-43). Flag off: the flag-off ViewState.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/clients/{client_id}/contacts` | `ContactsPage` (P-36 envelope + `summary` + `delegated`) | `contact.read` | every firm role that works the client's engagements; agent and system deny |
| read | `GET /v1/contacts/{contact_id}` | `ContactDetailOut` (O2 drawer) | `contact.read` | as above |
| write | `POST /v1/clients/{client_id}/contacts` · `PATCH /v1/contacts/{contact_id}` | `ContactIn` / `ContactPatchIn` → `ContactOut` | `contact.manage` | firm admin, partner, engagement partner, manager, client service |
| write | `POST /v1/contacts/{contact_id}/invitations` (+ `Idempotency-Key`) | `InvitationIn` → `InvitationOut` (never the token) | `client_access.grant` | firm admin, engagement partner, manager, client service; `mfa_recent`; G2 for the acting member on an attest client (ADR-164) |
| write | `POST /v1/invitations/{invitation_id}/resend` · `/revoke` | `InvitationOut` · `InvitationRevokedOut` | `client_access.grant` · `client_access.revoke` | as invite; revoke `mfa_recent` |
| write | `PUT /v1/contacts/{contact_id}/access` | `ContactAccessIn` → `ContactAccessOut` | `client_access.grant` | as invite |
| write | `POST /v1/contacts/{contact_id}/unlock` | `ContactUnlockedOut` | `contact.unlock` | firm admin, security admin, engagement partner, manager, client service |

## Status
`invitation`: Active (green-tint) · Invited (amber, sub-line "Sent {date} · expires {date}") · Not invited (neutral) · Locked (red-tint) (`status-vocabulary.yaml`). MFA "On" · "—".

## Copy
Copy keys live in `screens/CLI-04/copy.ts`; strings verbatim from spec.md.

| Key | String |
|---|---|
| `pane.title` | "Contacts & access" |
| `search.placeholder` | "Search contacts" |
| `header.counts` | "{active} active · {invited} invited · {notInvited} not invited" (a: "3 active · 1 invited · 2 not invited") |
| `header.preview` | "Portal preview" |
| `header.invite` | "+ Invite…" |
| `columns` | "Contact" · "Roles" · "Scope" · "Portal" · "MFA" · "Last seen" |
| `row.resend` · `row.invite` | "Resend" · "Invite…" |
| `row.menu` | "Change scope…" · "Unlock…" · "Revoke…" |
| `footer.delegated` | "Requests delegated: {parts} = {total} · PBC received {received} of {total}" (a: "Requests delegated: 10 + 9 + 2 + 2 + 1 = 24 · PBC received 11 of 24") |
| `sheet.title` · `sheet.titleChange` | "Invite to portal" · "Change access — {name}" |
| `sheet.send` | "Send invite" |
| `sheet.fieldsets` | "Who" · "What they can see" · "Security" · "Email preview" |
| `sheet.onlyDelegated` | "Only delegated requests" |
| `sheet.signIn` · `sheet.mfa` · `sheet.expires` | "Email code" · "MFA required" · "14 days" |
| `sheet.note` | "{org} will see only these {count} requests. They will not see the plan's other documents, materiality, review notes or other clients." |
| `toast.sent` | "Invite sent to {org}" |
| `locked.sub` (d) | "3 incorrect codes · {time}" (DF-24) |
| `revoke.title` · `revoke.body` | "Revoke portal access for {org}?" · "Their invite stops working immediately. Requests stay assigned to {client}." |
| `revoke.confirm` · `revoke.cancel` | "Revoke" · "Cancel" |
| `g.nonAttest` | "Non-attest client: no SKE designation required" |
| `tooltip.ske` | "SKE designee: the person with skills, knowledge and experience who oversees nonattest services — attest clients only" |

Contact names, emails, roles, scope lines, request titles and the email preview body are seed and database-template data, never `copy.ts` (the invitation email is the firm's Invitation template, C16).

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Subbar "‹ All Clients" ("Opens CLI-01 · all clients") | CLI-01 `to.CLI01()` | fixture (P-07-T21) |
| "Portal preview" ("Opens POR-02 rendered as a contact") | POR-02 | fixture (P-08); a read-only preview frame |
| Client subbar and tabs | CLI-02 `to.CLI02({ clientId })` | planned (P-07-T19) |
| A delegated request in the drawer | AUD-03 | planned (A-01) |
| Name click; "Invite…"; "Change scope…"; "Revoke…"; "Unlock…" | the O2 drawer, the O3 sheet, the 400 Dialog (local) | in-screen |

Inbound: CLI-02 (Contacts & access tab, Portal "→"), CLI-01 (Portal pill), ENG-02 (Client Portal "Portal ›"). All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- CLI-04 acceptance: the portal grammar matches close-overview's "Client Portal" group and the 500-wide O3 sheet with a 56 header (✕ · title · dark action) and fieldset cards.
- CLI-04 acceptance: delegated request counts sum to 24 (10 + 9 + 2 + 2 + 1) and the footer ties to PBC 11 of 24.
- CLI-04 acceptance: Dana Kowalski is plan administrator, signer and SKE designee; Harborline, the directed trustee and custodian, provides the §103(a)(3)(C) certification; only 402(g)/415 limit testing is requested (QACA safe harbor).
- CLI-04 acceptance: third parties are scoped to delegated requests with a lock icon; confirmation respondents are excluded from the portal.
- CLI-04 acceptance: status pills read Active green-tint, Invited amber, Not invited neutral, Locked red-tint.
- CLI-04 acceptance: no avatars; tags are the neutral tag with an inset hair.

## Figures
- Header 3 + 1 + 2 = 6 rows (`ContactsPage.summary`), proved by the CLI-04 a scenario footing test and the P-07-T18 consumer suite.
- Delegated 10 + 9 + 2 + 2 + 1 = 24; received 11; Northwind open requests 13 = 24 − 11 (P-07 §5 seed figures).

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, avatars, exposing materiality or other clients to third parties, letting the agent send invites, bordered inputs, native selects; "Accrued" in the email preview (DEC-01).

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| d-copy | "5 incorrect codes" becomes "3 incorrect codes" | Lockout is 3 codes → 15 minutes | DF-24 |
| d-viewer, e-viewer | The README lists Sam Ortiz as viewer of d and e; the screen is the firm's, so the viewer is Grace Holloway acting on Sam Ortiz's row | A client user never sees CLI-04 | P-07 §5 fixture table (CLI-04 a–g · grace-holloway) |
| unlock | Staff sign-in locks are not unlocked here | Only IT/Security (`security_admin`) unlocks staff | DF-24 |
| email | The preview renders the firm's database Invitation template, not fixed copy | Email templates are database content | C16, AGENTS 16 |
| expiry | Link expiry is fixed at 14 days (the ⇕ offers no other value yet) | ADM-02 expiry 7 → 14 | DF-24, DEC-226 |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a b c g | C (P0 lock before M8) | — | mask d's sub-line (DF-24) |
| d e f | C | — | |

## Open gaps
None open. The footer's `parts` are the non-zero per-contact counts in row order (DEC-226).
