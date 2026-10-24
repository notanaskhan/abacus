# ADM-10 · Portal branding & client experience

| Field | Value |
|---|---|
| Route and params | Firm `/settings/portal` (T12 frame, section `portal`; R-01 §5.1); `?ov=email-template:<key>` opens the O2 480 template editor drawer (e). The preview opens in a new tab at `/settings/portal/preview?as=<contact id\|sample>&device=desktop\|phone`. Artboards: `/components/screens/ADM-10?st=a…g` |
| Template and host frame | T12 `SettingsLayout` (F-05-T45; the ADM-01 settings frame, "Portal" selected) with a form pane (fieldsets 520) and a sticky live preview column (570) that renders POR-02's portal components (T7 split at 0.4, T7-M at 0.7) inside the firm app, never an iframe or a portal session · `Wave 3 - Admin & Governance.dc.html#adm10` |
| Surface | firm (Grace Holloway, Firm Admin). The preview frame and the email preview card are client-facing renderings: white-labelled, Brightwater Hale only |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ADM-10 Portal branding and client experience/` (README.md, spec.md; no revision.md) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | R-01 · contract R-01-T03; contract stub R-01-T16 (C16 v1.1, `docs/contracts/portal-settings.md`); consumer tests R-01-T17; glossary R-01-T04; template versions R-01-T19 (N); preview and lint R-01-T23 (N); follow-up policy R-01-T24 (N); portal settings and preview R-01-T26; sender domains R-01-T27 (N); data R-01-T22; frontend a–g R-01-T28 (reuses POR-20's editor from R-01-T25); independent AC tests R-01-T29 and R-01-T30; parity and accessibility R-01-T31; Playwright R-01-T32; pilot onboarding R-01-T34; delta #1 readiness R-01-T35 |
| Manifest status | planned (`routes/manifest/adm.ts`); fixture once R-01-T28 builds it |

Code to come (R-01 §5.2): `src/screens/ADM-10/{index.tsx, scenarios.ts, copy.ts, ADM-10.test.tsx}`, `src/domain/portal/PortalPreviewFrame.tsx`, `src/fixtures/handlers/portal-settings.ts`, `e2e/screens/adm-10-portal-settings.spec.ts`; the drawer reuses `src/domain/communications/{EmailPreview.tsx, templateBlocks.ts, variables.ts}`.

**White label (DEC-01, ADR-133, DEC-59, ADR-163).** This is a firm screen, so the firm app may show the word Accrued: the toggle label "“Secured by Accrued” footer" is firm-side. Nothing inside the preview frame or the email preview card names Accrued while that footer is off (the default): not the portal toolbar, the footer, the sender or a host. The accent is locked to espresso; the brand type has no colour field (chapter 04 §3.10, ADR-155). Branding, templates and the support contact are database content set here, never constants.

**Preview never widens access (DEC-20, ADR-024).** "Preview as" lists only contacts on clients the viewer can already read under `visible()`; otherwise it offers a sample client rendered from the firm's settings and fixed sample data. The preview is read-only, opens no portal session, impersonates nobody, reaches no mutation route and audits `portal.preview_viewed`.

## States

Fixture scenarios (R-01-T22, `fixtures/scenarios/ADM-10.ts`, data in `fixtures/seed/email-templates.ts` and the portal-settings handler), footed by the R-01-T22 scenario footing test (planned; Claire's 2 open items = Intake 2; "6 of 6 published · 1 with draft changes"; next reminder Mon Sep 21).

7 artboards in the handoff (README letters a–g, canonical; g has no spec letter), 7 built here.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | grace-holloway (Grace Holloway, Firm Admin); preview as `claire-feld` | Mon Sep 14, 2026, 9:24 AM CT | E0 | Published portal settings, no draft (Publish disabled); sender domain `brightwaterhale.com` verified; follow-up policy 7 days · max 4 · weekdays 9:00 AM recipient's time; templates 6 published, Reminder with a v4 draft (the preview email shows published v3); Claire's last reminder Mon Sep 14 9:00 AM, next Mon Sep 21; device desktop | fixture (T28) |
| b | grace-holloway; preview as `claire-feld` | same | E0 | A portal-settings draft with cadence 5 days (`PUT …/draft`, `expected_version` = published): "Unsaved changes", Publish enabled; `next_send_at` Sat Sep 19 shifted to Mon Sep 21 | fixture (T28) |
| c | grace-holloway; preview as `claire-feld` | same | E0 | Data of a; `device=phone`: POR-02 in T7-M at 0.7 with the bottom tab bar and counts (Documents 2 · Messages 1) | fixture (T28) |
| d | grace-holloway; preview as `claire-feld` | same | E0 | `sending_domains` row for `brightwaterhale.com` in `pending_dns` (DKIM CNAMEs and MAIL FROM `bounce.brightwaterhale.com` records not yet found): amber "Pending DNS", the records, and the neutral fallback lines; the sender and the preview email use the neutral sender | fixture (T28; data T27) |
| e | grace-holloway | same | E0 | `?ov=email-template:reconnect_request`: v1 published, no draft ("Publish v2" disabled until an edit); preview sample Arjun Mehta · Bluestem Analytics · Sage Intacct | fixture (T28) |
| f | grace-holloway; preview as `claire-feld` | same | E0 + publish | `POST …/portal-settings/publish` of b's draft: a new insert-only `portal_settings_versions` row with cadence 5; no draft (Publish disabled); toast | fixture (T28) |
| g | grace-holloway; preview as `tess-moreno` (Tess Moreno, Owner, Copperleaf Coffee Roasters, Inc.) | same | E0 | Preview of an entity client: Approvals in the nav; "Upload 2 documents for the August close" overdue (due Sep 5); August 2026 Close requests 7 of 9; Tess's last reminder Fri Sep 11, 9:00 AM MT, next Fri Sep 18 | fixture (T28) |

Personas: `grace-holloway`, `claire-feld`, `tess-moreno`, `dana-kowalski` and `meera-shah` exist in the TS seed (the "Preview as" list is Claire Feld · Tess Moreno · Dana Kowalski · Meera Shah); the e sample Arjun Mehta (Bluestem Analytics, LLC, already a seed client) is added by R-01-T22 if absent.

Non-artboard states (data conditions, never an `st` prop):

| State | Data condition | Rendering |
|---|---|---|
| Loading | `GET /v1/firm/portal-settings` pending | F-05 ViewState skeleton fieldsets; the preview column shows a skeleton frame |
| Error | the settings read fails | F-05 ViewState error row (C-20) with Retry; a failed preview read fails only the preview column |
| Flag off | `portal.settings_editor` false | read-only published values: no Replace…, Discard or Publish; toggles and ⇕ menus inert; template rows open the drawer read-only; the preview still renders; import is unaffected (copy key `flagOff.note`, string written by T28) |
| Not allowed | Staff, any role without `portal.settings.read`, and the agent: the matrix denies (`403`) | the T12 nav hides Portal; a deep link renders the C-20 not-allowed pane (a firm-level settings page, not a hidden record) |
| Read only | `practice_leader`: `portal.settings.read` without `manage` | values shown, controls absent from `allowed_actions` |
| Preview target not visible | `?as=` names a contact on a client the viewer cannot read under `visible()` (a walled client, or no `client_service` or membership): `404` | the picker never lists that contact; a forged `as` renders not-found in the preview column (INV-3) |
| No visible contact | nothing to preview as | the picker offers "Sample client" (R-01 Story 8.2) rendered from the published settings and fixed sample data (copy key `preview.sample`) |
| Stale draft | `PUT …/draft` or `POST …/publish` answers `409` on a stale `expected_version` | the draft reloads with the copy key `error.staleDraft` (string written by T28) |
| Template lint | in the drawer, test send or publish answers `422 template_lint_failed` | findings inline on their block, as POR-20 (`lint.<code>`) |
| Sender domain failed | 72 hours without DKIM and MAIL FROM verification | the domain row shows the failed status with its reason (copy keys `domain.failed`, `domain.failedReason`, strings written by T28); mail keeps the neutral sender with Reply-To |
| Sender flag off | `communications.firm_sender_domain` false while the domain is verified | Sender reads the neutral sender with the firm display name and Reply-To (`sender.replyTo`, string written by T28) |
| Fresh MFA | publish, logo, sending-domain create, check or revoke without a recent MFA | the shared step-up prompt (F-03), then the action retries |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/firm/portal-settings` | `{published {version, brand {portal_name, logo_url, accent: espresso (fixed), portal_host (read-only), sender, secured_footer}, client_experience {allow_upload_something_else, phone_capture, show_team_card, show_progress, support_contact}, follow_up_policy {cadence_days, max_reminders, send_at, weekdays_only, stop_when_marked_done, mode}}, draft {expected_version, …}?, next_reminder {sample_contact_id, last_sent_at, next_send_at, shifted_from?}, allowed_actions[]}` | `portal.settings.read` | `firm_admin`, `practice_leader`; every other firm role and the agent deny |
| write | `PUT /v1/firm/portal-settings/draft` · `DELETE …/draft` | save or discard the draft with `expected_version` (409 on stale); audits `portal_settings.draft_saved` | `portal.settings.manage` (`mfa_recent: required`) | `firm_admin` |
| write | `POST /v1/firm/portal-settings/publish` (`Idempotency-Key`; fresh MFA) | one unit of work: insert-only `portal_settings_versions` row, brand through P-08's `set_branding` / `set_logo`, client experience, follow-up policy; audits `portal_settings.published`; outbox `portal_settings.published {version}` | `portal.settings.manage` | `firm_admin` |
| write | `POST /v1/firm/portal-settings/logo` | draft logo through P-08's `set_logo` (server-side re-encode) | `portal.settings.manage` | `firm_admin` |
| read | `GET /v1/firm/portal-settings/preview?as=&device=desktop\|phone` | P-08's POR-02 projection (`PortalHomeOut`) in preview mode with the draft branding; read-only; `404` for a contact outside `visible()`; audits `portal.preview_viewed` (contact id or `sample`) | `portal.preview` (condition `preview_target_visible`) | `firm_admin` |
| read | `GET /v1/firm/follow-up-policy` | policy and `next_send_at` for the preview contact (weekday shift, recipient time zone; the same pure function the scheduler uses) | `portal.settings.read` | `firm_admin`, `practice_leader` |
| read | `GET /v1/firm/email-templates` | the six rows with pills and the footer count (as POR-20) | `email_template.read` | `firm_admin`, `practice_leader` |
| read / write | `GET …/email-templates/{key}`, `PUT …/{key}/draft`, `POST …/{key}/preview`, `POST …/{key}/test-send`, `POST …/{key}/publish` | the e drawer, same shapes as POR-20 | `email_template.read` / `edit` / `test_send` / `publish` | `firm_admin` (publish `mfa_recent: required`) |
| read | `GET /v1/firm/sending-domains` | `items[{id, domain, from_local_part, status ∈ pending_dns\|verified\|failed, records[{type, name, value, status}], reason?}]` | `sending_domain.read` | `firm_admin`, `security_admin` |
| write | `POST /v1/firm/sending-domains {domain, from_local_part}`, `POST …/{id}/check`, `DELETE …/{id}` | SES identity with Easy DKIM and custom MAIL FROM; `SendingDomainVerification` checks every 15 minutes for 72 hours; audits `sending_domain.created` / `verified` / `failed` / `revoked` | `sending_domain.manage` (`mfa_recent: required`) | `firm_admin`, `security_admin` |

## Status
Status objects shown, from `docs/product/status-vocabulary.yaml` where they exist:
- Sender domain: green-tint "Verified" (a–c, e–g) and amber state "Pending DNS" (d). No `sending_domain` object exists in the vocabulary yet; DF-31 lists "domain verification (Verified · Pending DNS)" as an addition, needed before R-01-T28 (see Open gaps).
- Email templates: green-tint "Published · vN" and amber "Draft changes · vN", as POR-20 (DF-31 "template draft").
- Next-reminder shift: "Sat, Sep 19 moves to the next weekday" in amber ink (a note, not a status pill).
- Inside the preview frame the statuses are POR-02's, in client words: "We're reviewing your return" (state amber), and in g "Overdue · due Sep 5" (`request` `overdue`, derived, red-tint) and "We're reconciling your accounts".
- Toggles on are `--green`.

## Copy
Copy keys live in `screens/ADM-10/copy.ts`; every string below is verbatim from the built artboards, and from spec.md where the screenshots do not reach (the lower Reminders rows and the Client experience fieldset are below the fold in every capture). The settings nav, "Back", "Firm settings" and "Brightwater Hale LLP" belong to the T12 frame (F-05-T45, ADM-01).

| Key | String |
|---|---|
| `header.title` | "Portal" |
| `header.unsaved` | "Unsaved changes" |
| `header.discard` / `header.publish` | "Discard" · "Publish" |
| `brand.title` | "Brand" |
| `brand.logo` | "Logo" · "Replace…" |
| `brand.portalName` | "Portal name" (value "Brightwater Hale", from settings) |
| `brand.accent` | "Accent" · "Espresso" (Lock icon) |
| `brand.accentHelp` | "Status colors stay legible because the accent is fixed." |
| `brand.portalHost` | the default host `brightwaterhale.<neutral-portal-domain>`, read-only, with "Custom domain — later" (R-01 Story 8.1; supersedes the handoff's "Custom domain" · "portal.brightwaterhale.com" · "Verified" row, DEC-59); the row label is written by T28 |
| `brand.sender` | "Sender" (value "Brightwater Hale <clients@brightwaterhale.com>" once verified) |
| `brand.securedFooter` | "“Secured by Accrued” footer" (toggle, off by default) |
| `templates.title` | "Email templates" |
| `templates.help` | "Preview at 600 and 390 px in POR-20." |
| `templates.footer` | "6 of 6 published · 1 with draft changes" (template `{published} of {total} published · {drafts} with draft changes`) |
| `reminders.title` | "Reminders" |
| `reminders.cadence` | "Cadence" · "Every 7 days until done" / "Every 5 days until done" (template `Every {n} days until done`) |
| `reminders.max` | "Maximum reminders" · "4, then notify the assigned preparer" (spec) |
| `reminders.sendAt` | "Send at" · "Weekdays · 9:00 AM recipient's time" (spec) |
| `reminders.stopWhenDone` | "Stop when the client marks the binder done" (spec) |
| `reminders.drafted` | "Drafted by Request Chaser" (spec) |
| `reminders.help` | "A person approves each template once; reminders then follow this cadence (AI policy row 9)." (spec) |
| `experience.title` | "Client experience" (spec) |
| `experience.uploadElse` | "Allow “Upload something else”" (spec) |
| `experience.phoneCapture` | "Phone capture" (spec) |
| `experience.teamCard` | "Show team card with names and roles" (spec) |
| `experience.progress` | "Show progress per work item" (spec) |
| `experience.support` | "Support contact" (value "Grace Holloway · (312) 555-0148", from settings) |
| `preview.title` | "Live preview" |
| `preview.device` | "Desktop" · "Phone" |
| `preview.as` | "Preview as" · "Claire Feld (sample)" (template `{name} (sample)`) |
| `preview.sample` | "Sample client" (R-01 Story 8.2; no handoff string) |
| `preview.label` | aria "Preview as Claire Feld — read only" (R-01 §5.6; template `Preview as {name} — read only`) |
| `emailCard.title` | "Reminder email" |
| `emailCard.edit` | "Edit in POR-20 ›" |
| `emailCard.meta` | "From" · "To" · "Last reminder" |
| `emailCard.lastSent` | "Mon, Sep 14, 9:00 AM" (g: "Fri, Sep 11, 9:00 AM MT"; time zone shown when it differs from the viewer's) |
| `emailCard.next` | "Next reminder Mon, Sep 21" (template `Next reminder {date}`; g "Next reminder Fri, Sep 18") |
| `emailCard.shift` | "Sat, Sep 19 moves to the next weekday" (template `{date} moves to the next weekday`) |
| `emailCard.sentFrom` | "Brightwater Hale LLP · Sent from portal.brightwaterhale.com" (template `{firm_legal_name} · Sent from {portal_host}`; R-01 renders the neutral host, see Open gaps) |
| `drawer.published` | "Published · v1" |
| `drawer.email` | "Email" · "Subject" · "Body" · "Button" · "Variables" |
| `drawer.variablesHelp` | "Click a variable to insert it at the cursor." |
| `drawer.preview` | "Preview" · "As Arjun Mehta · Bluestem Analytics · Sage Intacct" (template `As {name} · {client} · {connection}`) |
| `drawer.sendTest` | "Send test to grace.holloway@brightwaterhale.com" (template `Send test to {email}`) |
| `drawer.publish` | "Publish v2" (template `Publish v{n}`) |
| `toast.published` | "Portal settings published · clients see changes on next visit" |
| `domain.pendingDns` | "Pending DNS" |
| `domain.verified` | "Verified" |
| `domain.records`, `domain.fallback`, `domain.failed`, `domain.failedReason`, `sender.replyTo`, `flagOff.note`, `error.staleDraft` | reserved; R-01-T28 writes them (the handoff's d helper is superseded by DEC-59, see Deviations) |

Template row labels (registry, ADM-10's own wording): Invitation / "CLI-04 invites, prospect intake" · Reminder / "Binders, close requests, PBC — on the cadence below" · Signature request / "SIG-02 envelopes" · Deliverable ready / "Returns, K-1s, statements, reports" · Confirmation request / "AUD-14 · single-use POR-17 link, no portal" · Reconnect request / "CLS-11 · expired ledger connections (POR-16)".

Rendered previews (data, not copy):
- **Reminder email card (a–d, f; published v3).** Subject "2 items still needed for your 2025 tax return"; "Hi Claire, we still need 2 items to finish your return:"; "Form 1095-C from Mercer Hill Health" · "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations"; button "Open your portal"; To "claire.feld@gmail.com". g: "2 items still needed for your August 2026 close"; "Hi Tess, we still need 2 items to finish your close:"; "Front Range Bank savings ••4436 statement — August" · "Square payouts report — August"; To "tess@copperleafcoffee.com".
- **e drawer (Reconnect request v1, as built).** Subject "Please reconnect your accounting system"; body "Hi {client_first_name}, your {connection_name} connection has expired, so new transactions aren't reaching {firm_name}. Sign in at {portal_link} and choose Reconnect. It takes about a minute."; button "Reconnect"; rendered "Hi Arjun, your Sage Intacct connection has expired, so new transactions aren't reaching Brightwater Hale. Sign in at portal.brightwaterhale.com and choose Reconnect. It takes about a minute." (see Open gaps for the v1 conflict with POR-20 i).
- **Preview frame.** POR-02's components and copy (`screens/POR-02/copy.ts`, `domain/portal`), rendered with Claire's or Tess's projection: "Good morning, Claire", "Upload 2 documents", "Go to Documents →", "2025 Tax Return" "We're reviewing your return", team Daniel Reyes · Samuel Ito · Kevin Osei; phone "Take a photo", "Upload something else →"; g "Good morning, Tess", Approvals, team Priya Raman · Raj Malhotra · Grace Holloway. ADM-10 owns none of these strings.

Accessibility labels (R-01 §5.6): the preview is labelled "Preview as Claire Feld — read only" and its controls are inert and announced as such; the O2 drawer traps focus, is labelled "Reconnect request", closes on Esc and returns focus to the row.

Copy bans in the preview frame and email card (R-01 §5.7): "Accrued" (footer off), the agent or "AI", confidence, firm status words, materiality, an amount, review notes, agent reasoning.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Settings nav "General" | ADM-01 `to.ADM01()` | planned (G-01/G-02) |
| Settings nav "People" | ADM-02 | planned |
| Settings nav "Offices & teams" | ADM-03 | planned |
| Settings nav "AI policy"; Reminders helper "(AI policy row 9)" | ADM-04 | planned |
| Settings nav "Consents" | ADM-05 | planned |
| Settings nav "Security" | ADM-06 | planned |
| Settings nav "Audit log" (every change here is audited and readable there) | ADM-07 | planned |
| Settings nav "Integrations" | ADM-08 | planned |
| Settings nav "Developer" | ADM-09 | planned |
| Settings nav "Quality" | ADM-11 | planned |
| Settings nav "Monitoring" | ADM-12 | planned |
| "Edit in POR-20 ›", "Preview at 600 and 390 px in POR-20." | POR-20 `to.POR20({templateKey})` | planned (R-01-T25) |
| Preview frame click ("Opens POR-02 as Claire Feld in a new tab · preview mode, no data changes") | POR-02, rendered at `/settings/portal/preview?as=&device=` in the firm app | fixture (P-08-T15) |
| Template rows › | O2 drawer `?ov=email-template:<key>` (e) | in-screen |
| "Desktop" · "Phone"; "Preview as" | the same screen, preview re-rendered | in-screen |
| "Replace…", "Discard", "Publish", sender domain add and check (d) | `POST …/logo`, `DELETE …/draft`, `POST …/publish`, `POST /v1/firm/sending-domains` | in-screen |
| Controls inside the preview frame and the email card (nav, "Go to Documents →", "Open your portal") | none: inert in preview | — |

Inbound: ADM-01 (Settings home, "Portal"), POR-20 ("‹ Firm settings" and "Portal & client experience"), and the T12 settings nav. The template row labels name CLI-04, SIG-02, AUD-14, POR-17, CLS-11 and POR-16 as words only; the spec's "later" links (CLI-04 invitation trigger, POR-16, POR-17) are not designed links and are not drawn. All targets are manifest IDs that `link-contract.test.ts` knows, and every designed link of ADM-10 in `handoff-links.json` (ADM-01 to ADM-09, ADM-11, ADM-12, POR-20, POR-02) is named above.

## Acceptance
- ADM-10 acceptance: the preview matches `platform-portal.png`'s brand slot and nav order (01 §4.2), with Approvals hidden for Claire Feld (individual client) and shown for Tess Moreno (g, entity client).
- ADM-10 acceptance: Claire Feld's preview shows exactly the 2 open requests from TPL-07 (Intake 2 on the firm side).
- ADM-10 acceptance: six templates with the same names, versions and pills as POR-20 (6 published; Reminder has draft changes v4), with the footer "6 of 6 published · 1 with draft changes" matching ADM-01.
- ADM-10 acceptance: reminder cadence 7 days, at most 4, weekdays 9:00 AM, identical to POR-20's Reminder schedule (DEC-74); sender `clients@brightwaterhale.com` once verified; "Secured by Accrued" off by default.
- ADM-10 acceptance: no Accrued mark or word in the preview frame or email card; the accent is locked to espresso.
- ADM-10 acceptance (R-01 Story 8.1): changing the cadence from 7 to 5 days saves a draft, enables Publish and shows "Next reminder Mon, Sep 21" with "Sat, Sep 19 moves to the next weekday", from the same pure function the scheduler uses; the same date shows after publish (R-01-T28).
- ADM-10 acceptance (Story 8.1): Publish with fresh MFA writes one insert-only settings version and applies brand, client experience and follow-up policy atomically, shows "Portal settings published · clients see changes on next visit", and audits `portal_settings.published` with Grace as actor.
- ADM-10 acceptance (Story 8.2): previewing a contact on a client the viewer cannot read answers 404 and the picker never lists it; with no visible contact the picker offers a sample client; no mutation route is reachable from the preview.
- ADM-10 acceptance (Story 8.3): adding `brightwaterhale.com` shows "Pending DNS" with the three DKIM CNAMEs, the MAIL FROM MX and SPF records, DMARC guidance and the fallback lines `brightwaterhale.<neutral-portal-domain>` and `brightwaterhale@<neutral-mail-domain>`; once verified the Sender reads the firm address.
- ADM-10 acceptance (Story 8.2, INV-1): Staff and the agent principal are denied every settings, preview and sending-domain action.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Claire's open items 2 | = POR-02 "Upload 2 documents" = POR-03 `open_count` = TAX-03 Intake 2 = the Reminder's two items | R-01-T22 scenario footing test (planned) |
| Templates | 6 of 6 published · 1 with draft changes (Invitation v3, Reminder v3 + v4 draft, Signature request v2, Deliverable ready v2, Confirmation request v1, Reconnect request v1) = POR-20 list = ADM-01 "6 of 6 · 1 draft change" | same |
| Next reminder (a) | last Mon Sep 14, 9:00 AM + 7 days = Mon Sep 21 | R-01-T24 `next_send_at` test |
| Next reminder (b, f) | last Mon Sep 14, 9:00 AM + 5 days = Sat Sep 19 → next weekday Mon Sep 21 | same; R-01-T28 full-stack check |
| Next reminder (g) | Tess's last Fri Sep 11, 9:00 AM MT + 7 days = Fri Sep 18 (recipient's time zone) | same |
| Maximum | 4 reminders, then the assigned preparer is notified (`follow_up.limit_reached`) | R-01-T24 |
| Copperleaf preview (g) | 2 open documents, overdue (due Sep 5); close requests 7 of 9 (= POR-02 d) | P-08-T08 footing; R-01-T22 |
| Phone badges (c) | Documents 2 · Messages 1 (= POR-02 M) | POR-02 scenario test M |

## AVOID
Each becomes a test in `ADM-10.test.tsx` ("ADM-10 avoid: …"): gradients in product UI, emoji, saturated blue, heavy shadows, invented colours (the accent is never changeable to another hue), lorem ipsum, Accrued branding in the portal header, firm internals in the preview (materiality, review notes, agent reasoning).

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DEC-59 | d applies to the **sender domain** in R-01 (three DKIM CNAMEs, MAIL FROM MX and SPF, DMARC guidance). The portal row shows the neutral default host `brightwaterhale.<neutral-portal-domain>` read-only with "Custom domain — later". The fallback lines read `brightwaterhale.<neutral-portal-domain>` and `brightwaterhale@<neutral-mail-domain>`, never `…accrued.app`. The handoff's d helper ("Add the CNAME record portal → brightwaterhale.portal.accrued.app …"), its sender "Brightwater Hale <clients@mail.accrued.app>", its footer "Sent from brightwaterhale.portal.accrued.app" and the a–c, e–g row "Custom domain · portal.brightwaterhale.com · Verified" are superseded | Neutral domains never contain "accrued"; custom portal domains come later; per-firm DKIM now | decision-log DEC-59; ADR-163; R-01 §2.1 |
| DEC-59 | "Secured by Accrued" footer defaults off. The firm app may show the word Accrued (the toggle label is firm-side); the preview frame's portal content and the email card never do while the footer is off | White label | decision-log DEC-59; ADR-163 §7 |
| — | g has no spec letter (added during the build) and is canonical | Handoff README rule | R-01 §2.1 |
| — | Accent locked to espresso; the brand type has no colour field | Branding is slots, not theming | chapter 04 §3.10; ADR-155 |
| — | The preview renders POR-02's portal components inside the firm app, never an iframe or a portal session; "opens POR-02 in a new tab" is the firm route `/settings/portal/preview` | Two origins; preview is read-only | chapter 04 §1.4; R-01 §5.1 |
| DEC-20 | "Preview as" lists only contacts the viewer can see under `visible()`, else a sample client; preview never widens a firm admin's access | ADR-024 unchanged | decision-log DEC-20 |
| DEC-74 | Reminders are the one firm follow-up policy (the same values as POR-20's Reminder schedule) with P-06's per-binder override; a person approves each template once; system-scheduled sends only behind `follow_ups.scheduled_send` | Follow-ups and reminder cadence | decision-log DEC-74 |
| DF-03 | c renders POR-02 in T7-M at 390 with the bottom tab bar Home · Documents · Sign · Messages · More (DEC-45) | Portal mobile scope | chapter 09 DF-03; decision-log DEC-45 |
| DEC-35, DF-15, DF-40, DEC-58 | Not on this screen (DEC-35 and DF-40 surface in POR-20; DEC-58 and DF-15 in POR-03/04/14) | — | R-01 §2.1 |
| — | The email card previews the **published** Reminder (v3), so its words differ from POR-20 a's v4 draft until v4 is published | v3 stays live until v4 publishes (spec Email templates row) | this contract |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c, e, f, g | C (threshold 0.20, maxDiffPixelRatio 3 %) | not run (unbuilt) | reported from S12; locked at R-01 exit (R-01-T31). Masks: the Brand host row and the email card's "Sent from" host (DEC-59, see Open gaps); the preview frame interior (covered by POR-02's own parity); e's drawer content region (v1 conflict); g's second open-item line pending the account-fragment decision |
| d | C | not run | reported only; DEC-59 host and sender copy masked (the Brand host row, the domain helper and records, the Sender row, the email card From and footer) |
| host | D | — | T12 frame (F-05), form pane x262–1388 with a 46 header (14.5/500 left title), fieldsets 520 with gap 12, preview column 570 (sticky), preview frame 570 × 356 (desktop at 0.4, phone at 0.7), email card 570 × 300 with a 400 email at 0.66, ValueRows 40, O2 drawer 480, toast 36 |

Tier B for T12 is F-05's (F-05-T45/T49).

## Open gaps
- **Superseded host in every artboard.** §5.5 masks DEC-59 copy on d only, but a–c and e–g also show "portal.brightwaterhale.com · Verified" in the Brand row and "Sent from portal.brightwaterhale.com" on the email card (and e's rendered body). R-01 renders the neutral host there. Decided here: R-01-T31 masks those regions on every artboard; the masks lift when custom portal domains ship.
- **Preview frame contents.** The handoff's preview is a mini POR-02 (to-do list with Upload… rows and a drop strip; "Take a photo" on the phone) that differs from POR-02's built TodoCard grid. Story 8.2 renders P-08's real POR-02 projection and components, so the frame interior is whatever POR-02 renders; it is masked here and proven by POR-02's parity.
- **Account fragment in g's reminder.** The Copperleaf item reads "Front Range Bank savings ••4436 statement — August", a request title carrying the last four digits of an account; POR-20's rule and Story 7.2's lint forbid account numbers in email. R-01-T23 decides whether a "••" last-four mask is an account number (fail closed is the default) and, if so, how `{open_items}` renders such titles; the line is masked until then.
- **Reconnect request v1 conflict.** e shows v1 as "Please reconnect your accounting system" with a variable body (sample Arjun Mehta, Sage Intacct); POR-20 i shows v1 as "Please reconnect American Express for your monthly close" (Tess Moreno, Amex). One v1 is seeded: decided in POR-20.md as POR-20 i's; e's drawer renders that row and its content region is masked. To confirm with AY before R-01-T22.
- **"Drafted by Request Chaser".** The toggle's mapping onto the policy mode (`draft_for_person` vs `send_on_schedule`, DEC-74) is R-01-T24's; while `follow_ups.scheduled_send` is off the only live mode is drafts a person sends, and the toggle reads as built.
- **Maximum reminders wording.** POR-20 reads "4"; ADM-10 reads "4, then notify the assigned preparer". Same value, each screen keeps its own string. POR-20's "Copy the assigned preparer" has no ADM-10 row (see POR-20.md).
- **"(sample)" suffix.** The built picker reads "Claire Feld (sample)"; Story 8.2 lists real visible contacts and a "Sample client". Kept as built for the fixture personas; R-01-T28 decides whether a real visible contact carries the suffix.
- **Strings with no handoff copy.** DNS records labels, fallback lines, failed status and reason, Reply-To, flag-off note, stale draft (409) and the "Custom domain — later" row label: keys reserved above; R-01-T28 writes them inside the copy bans and records them here.
- **Status vocabulary.** `sending_domain` (Verified · Pending DNS · failed) and the email-template pills are DF-31 additions not yet in `status-vocabulary.yaml`; they must land before R-01-T28.
- **Lower fieldsets not captured.** The Reminders rows below Cadence and the whole Client experience fieldset are below the fold in every screenshot; their strings come from spec.md and are rechecked against the canvas when R-01-T28 builds.
- **"Back".** The T12 frame's "‹ Back" has no designed target; it follows history (F-05's frame).
