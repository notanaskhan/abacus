# POR-01 · Portal sign-in

| Field | Value |
|---|---|
| Route and params | `/sign-in` (a, b, c, c′, e, f, g) with `#link=<token>` for reminder links (moved to tab storage, never a query string) and `?return=` for return-to; `/accept` (d) with `#token=<token>`, reusing `takeTokenFromFragment` from `ClientAccept.tsx` (P-08 §5.1). Portal entry, origin root, no `/client` prefix (DEC-59). Artboards: `/components/screens/POR-01?st=a…g` |
| Template and host frame | T15 auth card (F-05 `AuthCard` 400 wide with `CodeInput` and Toggle; no toolbar) + the 390 layout · `Wave 2 - Client Portal.dc.html#por01` |
| Surface | portal (white-labelled: the firm's mark, name, address and people; nowhere "Accrued") |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-01 Portal sign-in - Brightwater Hale/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-08 · contract P-08-T03; glossary P-08-T04; ADR P-11 P-08-T30; branding P-08-T05; WorkOS port P-08-T06; portal entry P-08-T07; data P-08-T08; a, b, e, f, g P-08-T09; BFF P-08-T10; auth client P-08-T11; c, c′ and d P-08-T19 (over MFA P-08-T17 and invitations v2 P-08-T18; AC suites T20 and T24); parity and accessibility P-08-T27 |
| Manifest status | fixture (`routes/manifest/por.ts`, `entry: true`, no firm path: the screen is served by the portal entry at `/sign-in`, `routes/portal/index.tsx`; P-08-T09). a, b, e, f, g and 390 are built; c, c′ and d are P-08-T19's |

Code (P-08-T07, T08, T09): `portal.html`, `src/entries/portal.tsx`, `src/routes/portal/index.tsx` (the portal's own route tree; P-08 §5.2 named it `public.tsx`), `src/portal/{PortalRoot,PortalShell,EntitySwitcher}.tsx`, `src/app-core/{portal-contracts,portal-session}.ts`, `src/domain/portal/{sign-in,shell,messages,index}.ts`, `src/screens/POR-01/{index.tsx, scenarios.ts, copy.ts, POR-01.test.tsx}`, `src/fixtures/{handlers/portal.ts, seed/portal-home.ts, scenarios/POR-01.ts, scenarios/POR-02.ts, install-portal.ts, portal.foot.test.ts}`, `scripts/portal-dist-check.mjs`, `e2e/screens/POR-01.spec.ts`. `src/app-core/auth/bff.ts` (P-08-T11, DEC-231): the in-memory token, refresh through the host cookie with `X-Abacus-CSRF`, 401 to `/sign-in?return=`, sign-out.

**White label (AGENTS frontend rule 7, DEC-01, ADR-133, DEC-59).** Portal code never renders "Accrued": not in copy, `title`, favicon, alt text, aria labels, error messages, email previews or bundle strings. The firm's name, mark, address, help and privacy links and support contact come from `GET /v1/portal/branding`; the "Secured by Accrued" footer is off (`secured_footer: false`). The L7 white-label crawl (F-05-T39) and the `vite build --mode portal` string check (P-08-T07) enforce it.

## States

7 artboards in the handoff (a–g), 7 built here, plus the DF-17 two-step setup state c′ and the DF-03 390 layout, which have no frame.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | claire-feld (Claire Feld, Feld household, taxpayer) | Mon Sep 14, 2026, 9:22 AM CT | E0 | No session on `brightwaterhale.<neutral-portal-domain>`; branding row for Brightwater Hale; email field prefilled `claire.feld@gmail.com` | built · fixture (T09) |
| b | claire-feld | same | E0 | `POST /v1/portal/auth/start` answered 202 with `resend_available_at` 42 s ahead; code `481027` typed (fixture only; real codes are random) | built · fixture (T09) |
| c | tess-moreno (Tess Moreno, Owner, Copperleaf Coffee Roasters, Inc.) | same | E0 | `verify` answers `{state: "mfa_required"}`: an active `owner` grant meets the MFA floor; TOTP factor enrolled | built · fixture (T19) |
| c′ | tess-moreno | same | E0 | `verify` answers `{state: "mfa_setup_required"}`: floor met, no factor yet (DF-17; not a lettered artboard) | built · fixture (T19), Tier D only |
| d | sam-ortiz (Sam Ortiz, Keystone Retirement Services) | Wed Sep 2, 2026 | E0 | Pending invitation from CLI-04 (`POST /v1/invitations/preview` 200): 9 Northwind Robotics 401(k) Plan requests delegated to Keystone; terms toggle off | built · fixture (T19) |
| e | claire-feld | Mon Sep 14, 2026, 9:22 AM CT | E0 | A reminder link issued Aug 20 (more than 14 days old) opened at `/sign-in#link=…` | built · fixture (T09) |
| f | claire-feld | same | E0 | One wrong code: `verify` answers `401 code_mismatch {tries_left: 2}` | built · fixture (T09) |
| g | claire-feld | same | E0 | Third wrong code: `423 sign_in_locked {locked_until}` 15 minutes ahead; support contact from branding (Grace Holloway) | built · fixture (T09) |
| 390 | claire-feld | same | E0 | Viewport 390 × 844 (DF-03; specified from the spec text, no frame was built) | built · fixture (T09), Tier D only |

Personas not yet in the TS seed (`tess-moreno`, and any of `sam-ortiz` the seed lacks) are added by P-08-T08; `claire-feld` exists.

Non-artboard states (C-20 kit; data conditions, never an `st` prop):

| State | Data condition | Copy |
|---|---|---|
| Code expired | `verify` answers `410 code_expired` (code older than 10 minutes) | `SIGN_IN_WORDS.codeExpired`: "That code has expired. Use Resend code to get a new one." |
| Resend too soon | `resend` answers `429 resend_too_soon {resend_available_at}` | `SIGN_IN_WORDS.resendTooSoon`: "A new code can be sent when the countdown ends."; the countdown restarts from the server's time |
| MFA wrong / locked | `401 mfa_mismatch {tries_left}` · `423 mfa_locked {locked_until}` | reuse f's helper and g's card |
| Sign-in paused | `503 sign_in_paused` (per-firm kill switch) | `SIGN_IN_WORDS.paused`: "Sign-in is paused for now. If you need help, contact {person} at {firm}." (without a contact: "Sign-in is paused for now. Please try again later.") |
| Unknown portal host | `GET /v1/portal/branding` returns neutral values (same shape) | `COPY.neutral`: "Use your email address. We'll send you a 6-digit code — no password needed.", "Codes expire after 10 minutes.", locked "For your security, sign-in is paused for 15 minutes."; no firm mark, name, address or person; the tab reads "Client portal" |
| Network error | request fails | `SIGN_IN_WORDS.network`: "We couldn't reach the sign-in service. Check your connection and try again." in the helper (the card stays; T09) |
| Flag off | `portal.sign_in_v2` false | legacy hosted OIDC sign-in (`ClientAccept.tsx` path) |
| Unbuilt landing (fixture builds) | landing screen is `planned` | "Not built yet" (manifest rule) |

The strings for these keys are not handoff copy: P-08-T09 wrote them on the C-20 grammar (what happened, then what to do) in `domain/portal/messages.ts` and `screens/POR-01/copy.ts`, recorded above, inside the portal copy bans below. Also not handoff copy: the spinner's accessible name "Sending your code", "1 try left" (the singular of f's helper) and "Not built yet" on a planned landing (fixture builds only).

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/portal/branding` | Public fields only: `firm_name`, `portal_name`, `logo_url`, `address_line`, `help_url`, `privacy_url`, `support_contact_name`, `secured_footer: false`, `sign_in {methods, mfa_floor}`, `maintenance_banner`; same shape for an unknown host; no tenant identifier | none · ADR P-45 exception | unauthenticated |
| read | `GET /v1/portal/branding/logo` | Server-re-encoded PNG, same-origin, ETag | none · P-45 exception (to add, OQ-2) | unauthenticated |
| write | `POST /v1/portal/auth/start {email, link_token? \| invitation_token?}` | Always 202 `{challenge_id, code_expires_at, resend_available_at}`, padded; email sent only for eligible contacts | pre-session | identical status, body and timing for any email (no enumeration) |
| write | `POST /v1/portal/auth/verify {challenge_id, code}` | `200 {state: signed_in, access_token, expires_in, landing}` · `200 {state: mfa_required \| mfa_setup_required, mfa_token}` · `401 code_mismatch {tries_left}` · `423 sign_in_locked {locked_until}` · `410 code_expired` · `503 sign_in_paused` | pre-session | — |
| write | `POST /v1/portal/auth/resend {challenge_id}` | New code, old code void, tries not reset · `429 resend_too_soon` | pre-session | — |
| write | `POST /v1/portal/auth/mfa {mfa_token, totp \| backup_code, trust_device}` | Second step · `401 mfa_mismatch` · `423 mfa_locked` | pre-session | floor roles only reach it |
| write | `POST /v1/portal/auth/mfa/setup` · `/mfa/setup/verify` | Enrol TOTP; 8 backup codes returned once | pre-session | — |
| write | `POST /v1/portal/links/renew {link_token}` | Always 202; new link only to the original address | pre-session | — |
| read | `POST /v1/invitations/preview {token}` | Firm, organisation, invitee, access summary (kind, item count, scope label), terms URL and version, expiry; one `404` for every failure | pre-session | — |
| write | `POST /v1/invitations/accept {token, terms_version}` | Creates the template's grants in one unit of work | `IDENTITY` (existing) | invitee only |
| write | `POST /v1/portal/auth/refresh` · `/sign-out` | Cookie + `X-Abacus-CSRF`; sign-out ends the session | cookie exception · `OWN` | — |

The landing comes from `/v1/me.portal` (`portal_scopes`, DEC-129): full shell → POR-02; third party only → POR-14; K-1 only → POR-13; TCWG only → POR-15; prospect → POR-18; component auditor → POR-23.

## Status
No status object is shown on POR-01. Contact `portal_state` (`active`, `locked`) is firm-side (CLI-04). Error codes map to words in `domain/portal/messages.ts` (ADR P-36 code → words), never to raw codes on screen.

## Copy
Copy keys live in `screens/POR-01/copy.ts`; every string below is verbatim from spec.md and the built artboards. Firm name, address, people and email addresses are branding and seed data, shown here as they render for Brightwater Hale.

| Key | String |
|---|---|
| `brand.name` | "Brightwater Hale" (branding `portal_name`) |
| `a.title` | "Sign in to your client portal" |
| `a.body` | "Use the email address Brightwater Hale has on file. We'll send you a 6-digit code — no password needed." (template `{firm}`) |
| `a.continue` | "Continue" |
| `footnote` | "Brightwater Hale uses secure sign-in. Codes expire after 10 minutes." |
| `footer` | "Help · Privacy · Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL" (Help and Privacy are links; the rest is branding `address_line`) |
| `b.title` | "Check your email" |
| `b.body` | "We sent a 6-digit code to claire.feld@gmail.com." (template `{email}`) |
| `b.signIn` | "Sign in" |
| `b.didntGet` | "Didn't get it?" |
| `b.resend` | "Resend code" (disabled with the countdown "0:42") |
| `b.differentEmail` | "Use a different email" |
| `c.title` | "Two-step verification" |
| `c.body` | "Enter the 6-digit code from your authenticator app." |
| `c.trust` | "Trust this device for 30 days" |
| `c.verify` | "Verify" |
| `c.backup` | "Use a backup code" |
| `d.title` | "Brightwater Hale invited you" |
| `d.body` | "Brightwater Hale LLP is auditing the Northwind Robotics 401(k) Plan and has asked Keystone Retirement Services for 9 items. You'll only see those requests." (template; firm, plan, organisation and count are data) |
| `d.kv` | "Name" · "Organization" · "Access" |
| `d.access` | "Requests delegated to you" |
| `d.terms` | "I agree to the Brightwater Hale client portal terms" ("Brightwater Hale client portal terms" is the link, with an ink-3 "→") |
| `d.accept` | "Accept and continue" |
| `e.title` | "This sign-in link has expired" |
| `e.body` | "Links work for 14 days. We can send you a new one." |
| `e.renew` | "Email me a new link" |
| `e.toast` | "New link sent to claire.feld@gmail.com" (template `{email}`) |
| `f.helper` | "That code didn't match. 2 tries left." (template `{n} tries left`) |
| `g.title` | "Too many attempts" |
| `g.body` | "For your security, sign-in is paused for 15 minutes. If you need help now, contact Grace Holloway at Brightwater Hale." (template; the person is branding `support_contact_name`) |
| `g.contact` | "Contact Brightwater Hale" |

Accessibility labels (P-08 §5.6): code group "Sign-in code", boxes "Digit n of 6"; the trust control is a `role="switch"` with its label.

Copy bans on this screen (P-08-T04 glossary rows, L2/L7): never "Accrued", "password", "task" (say "to-do"), an agent name or a firm status word. UI terms are "Client portal", "Sign-in code" and "Two-step verification".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Sign in / Verify / Accept and continue, full-shell scope (Claire Feld, Tess Moreno) | POR-02 `to.POR02()` | planned (P-08-T15 and T23 build POR-02) |
| Sign in, third party only (Sam Ortiz after d) | POR-14 | planned (R-01) |
| Sign in, K-1 recipient only | POR-13 | planned (T-02) |
| Sign in, TCWG member only | POR-15 | planned (R-02) |
| Sign in, prospect | POR-18 | planned (R-03) |
| Sign in, component auditor | POR-23 | planned (A-09) |
| "Use a different email" (b) | a (local state) | in-screen |
| "Use a backup code" (c) | backup-code entry (local state) | in-screen |
| "Email me a new link" (e) | toast (E3) | in-screen |
| "Contact Brightwater Hale" (g), "Help", "Privacy" | branding `help_url`, `privacy_url` (firm's own pages) | external, from branding |
| "Brightwater Hale client portal terms" (d) | the invitation's terms URL (preview payload) | external, from the invitation |

Inbound: POR-20 emails (Invitation, Reminder, Signature request, Deliverable ready) and CLI-04 "Send invite". The handoff's link graph records no outbound link from POR-01 (README "None found"); the role-routed landings above come from spec.md INTERACTIONS and P-08 Story 2.3. All targets are manifest IDs that `link-contract.test.ts` knows. In fixture builds an unbuilt landing renders "Not built yet"; in production a `planned` landing cannot be reached because no invitation for that role can be issued yet (P-08 §2.2).

## Acceptance
- POR-01 acceptance: one 400-px card on `#F8F8F6`, radius 14, `e2`; firm mark + "Brightwater Hale" above the title; nothing says Accrued.
- POR-01 acceptance: passwordless: email → 6 boxes (44×52, `#EFEEEB`) → optional authenticator step; no password field anywhere.
- POR-01 acceptance: the two-step frame is shown for an owner (Tess Moreno), not for every client — policy-driven, per firm.
- POR-01 acceptance: the invite-acceptance frame scopes Sam Ortiz to "9 items" for Northwind only (matches CLI-04 and POR-14).
- POR-01 acceptance: error is red-ink text + inset ring only; the locked state names a firm person (Grace Holloway), not a vendor.
- POR-01 acceptance: the 390 frame keeps the same hierarchy with the primary button pinned near the bottom.
- P-08 Story 2.1: an unknown email, a staff member, a contact with no active grant, another firm's contact and a locked email get the same status, body shape and timing; no email is sent.
- P-08 Story 2.1: the sixth digit submits once; the 600 ms spinner shows on Continue.
- P-08 Story 2.2: a resend voids the old code and does not reset the tries; the third wrong code locks for 15 minutes.
- P-08 Story 3.3 (DF-17): c′ shows a QR code and manual key, verifies a first code, then shows 8 backup codes once with a confirm step; declining leaves no session.
- P-08 Story 5.1: "Email me a new link" sends only to the address the old link was sent to.
- P-08 §5.6: paste works in the code input (`autocomplete="one-time-code"`, `inputmode="numeric"`); the helper is a polite live region; the lock moves focus to the title; every target ≥ 24 px, including the 390 boxes.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Tries | 3 wrong codes → lock; f shows 2 left after 1 miss | T10 AC suite; scenario test f, g |
| Lock | 15 minutes on `kernel.clock` | T10 AC suite |
| Code | expires after 10 minutes; resend countdown 0:42 at b | T10 AC suite; scenario test b |
| Link | 14 days (e: issued Aug 20, opened Sep 14 = 25 days) | T21 AC suite; scenario test e |
| Invitation | 9 items for Keystone = POR-14 and CLI-04 | T08 footing test |
| Trusted device | 30 days, the firm may set fewer, never more | T17 AC suite |
| Backup codes | 8, shown once | T17 AC suite |

## AVOID
Each becomes a test in `POR-01.test.tsx` ("POR-01 avoid: …"): gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, password fields, social sign-in buttons for clients, the Accrued name or mark, CAPTCHA art, red banners for ordinary errors, bordered inputs.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DEC-35 | Lock after 3 wrong codes per email across resends; the "5 attempts per code" cap in DEC-35 never binds | Matches f ("2 tries left") and g; stricter wins (P-08 OQ-3) | `docs/product/decision-log.md` DEC-35; P-08 §11.2 OQ-3 |
| DEC-35 | Invitation and reminder links last 14 days, single use (SPEC-015 said 7); trusted devices 30 days | X-11 settled by DEC-35 | decision-log DEC-35 |
| DEC-58(d) | No bell or notification entry on the portal; a lock raises no in-app notice | No portal bell; email plus the Home list | decision-log DEC-58 |
| DEC-59 | The card sits on `<slug>.<neutral-portal-domain>`, never a host containing "accrued"; `/v1` same-origin; the host is a branding hint only; no "Secured by Accrued" footer | White label; X-12 | decision-log DEC-59; ADR P-11 (P-08-T30) |
| DF-17 | Adds c′ two-step setup (QR, manual key, first code, 8 backup codes with confirm), composed on the T15 kit with no handoff frame; c's trust toggle is the 30-day trusted-device state | DEC-34 MFA floor; the design follow-up is not delivered | P-08 §0.1 DF-17; reviewed by the builder until the DF-17 revision lands |
| DF-24 | e keeps "Links work for 14 days"; lock copy stays "3 codes → 15 minutes" as g words it | Copy reconciled with DEC-35 | P-08 §0.1 DF-24 |
| DF-03 | The 390 layout is built from spec.md MOBILE 390 (card full width minus 16, padding 24 20, boxes 42×50 gap 6, primary pinned 16 px above the safe area); no frame exists | DEC-45 portal responsive scope | P-08 §0.1 DF-03 |
| — | The canvas's fixture code 481027 exists only in fixtures; real codes are random | Security | P-08 §5.4 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a–g | C (threshold 0.20, maxDiffPixelRatio 3 %) | not run (a, b, e, f, g built; axe 0 serious at 1400, 720 and 390 in `e2e/screens/POR-01.spec.ts`) | reported, then locked (blocking) at P-08 exit (T27); b masks the countdown; d at the Sep 2 clock |
| c′, 390 | D | — | no PNG; Tier D only |
| host | D | — | card 400 wide, radius 14, top 196, padding 28 28 24; code boxes 44×52 r10 gap 8 (42×50 gap 6 at 390); button 36 h; mark 34 px; body 13/15.6 Geist |

Tier B for T15 is F-05's (F-05-T49).

## Open gaps
- **Pre-session routes (T09, T11).** Start, verify, resend, refresh and sign-out are served (P-08-T10) and called through the generated functions (`portalStart`, `portalVerify`, `portalResend`, `portalRefresh`, `portalSignOut`; P-08-T11). Branding (served, P-08-T05) and `/v1/portal/links/renew` and `/v1/invitations/preview` (unserved, T21 and T18) still use the drafts in `app-core/portal-contracts.ts` and named paths on the generated `client`.
- **Expired reminder link (T09).** The contract has no answer that says a reminder link is expired (`start` is 202 for any input). The fixture answers `POST /v1/portal/auth/start {link_token}` with `410 link_expired` for a link older than 14 days, and the screen shows e for it. P-08-T10/T21 must add this answer (or a link-status read) to the pre-session family.
- **Fixture email (T08).** The seed's mailboxes are on the synthetic sink domain (SPEC-307 AC-5), so the fixtures show `claire.feld@sink.brightwaterhale.test` where the handoff shows `claire.feld@gmail.com`. Parity masks the address.
- **Firm mark (T09).** The branding has no mark slot, only `logo_url`; without a logo the card draws the firm's initials ("BH") where the handoff draws Brightwater Hale's wave mark. The wave arrives as the firm's uploaded logo (ADM-10).
- **Keystone's 9 items (T08).** d's 9 comes from CLI-04's delegation split (10 + 9 + 2 + 2 + 1 = 24, footed against Northwind's 24 requests); the interim seed's per-request owner column names Keystone on 7. The seed's owners follow the Python scenario when F-04-T31 exports it.
- **Secured-footer label in the portal dist (T07).** The design system's wordmark carries the product's name as its default accessible name, and the portal kit (AuthFrame, AppShell) imports the opt-in "Secured by" footer, so one string reaches dist/portal. `scripts/portal-dist-check.mjs` allows exactly that one occurrence; loading the footer only when `secured_footer` is on (an F-05 follow-up) removes it.
- **Legacy client screens in the portal entry (T07).** The legacy `ClientHome`, `ClientEngagement` and `ClientAccept` stay in the firm bundle at `/client/*` (`routes/portal.tsx`): the INV-4 lint forbids the portal entry from importing `src/legacy`, so they are not mounted there. R-01 and P-08-T28 replace and retire them.
- **README vs spec clock for a.** README renders a as "Mon Sep 14, 9:22 AM", the others "Mon 14 Sep 2026, 9:22 AM": the same instant; the contract uses Mon Sep 14, 2026, 9:22 AM CT for a–c and e–g and Wed Sep 2, 2026 for d (P-08 §5.4).
- **Non-artboard copy.** No handoff string exists for code expired, resend too soon, sign-in paused, the unknown-host neutral card or c′. Decided: the keys are reserved here; T09 and T19 write the strings on the C-20 grammar, record them in this contract and keep them inside the copy bans. They are not handoff copy and are flagged as such in `copy.ts`.
- **OQ-2.** The pre-session routes and `/branding/logo` must be on the ADR P-45 or P-54 exception list before T05/T10 merge (P-08 §11.2).
- **POR-23 landing.** The component-auditor landing (`/component-room`) is P-08 Story 2.3, not a designed link; it is listed so the landing table is complete.
