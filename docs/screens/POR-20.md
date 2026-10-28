# POR-20 · Transactional email templates (Reminder)

| Field | Value |
|---|---|
| Route and params | Firm `/settings/portal/email-templates/$templateKey` (R-01 §5.1); `$templateKey` is a registered firm-editable key (`invitation`, `reminder`, `signature_request`, `deliverable_ready`, `confirmation_request`, `reconnect_request`, then keys other epics register through R-01's slot); `?w=600\|390\|phone` (default `600`; `phone` draws the 470 × 900 mail-client frame). Send test… is an O3 sheet over the screen. Unknown key: `404`. Artboards: `/components/screens/POR-20?st=a…l` |
| Template and host frame | T10 document on well (structure 470 + paper 896 holding a 600 px email well) inside the SHL-01 firm shell with the firm pill pressed and no nav item active; the well renders through R-01's interim `EmailPreview` until F-06-T16 re-homes it onto T10e (`DocumentOnWell variant="email"`) · `Wave 3 - Client Portal.dc.html#por20` |
| Surface | firm (Grace Holloway, Firm Admin). Everything inside the well is client-facing email: white-labelled, Brightwater Hale only |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-20 Transactional email templates - Reminder/` (README.md, spec.md; no revision.md) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | R-01 · contract R-01-T03; contract stub R-01-T16 (C16 v1.1, `docs/contracts/email-templates.md`); consumer tests R-01-T17; glossary R-01-T04; template versions and renderer R-01-T19 (N); preview, lint, test send and import R-01-T23 (N); follow-up policy R-01-T24 (N); sender domains and the client-mail gate R-01-T27 (N); data R-01-T22; frontend a–l R-01-T25; independent AC tests R-01-T30; parity and accessibility R-01-T31; Playwright j16 step 4 and the screen spec R-01-T32; pilot import R-01-T34; well re-home F-06-T16 |
| Manifest status | planned (`routes/manifest/por.ts`); fixture once R-01-T25 builds it |

Code to come (R-01 §5.2): `src/screens/POR-20/{index.tsx, scenarios.ts, copy.ts, POR-20.test.tsx}`, `src/domain/communications/{EmailPreview.tsx, templateBlocks.ts, variables.ts}`, `src/fixtures/handlers/email-templates.ts`, `src/fixtures/seed/email-templates.ts`, `e2e/screens/por-20-email-templates.spec.ts`.

**White label and content (AGENTS rules 7 and 16, DEC-01, ADR-133, DEC-59, ADR P-25).** The firm app around the well may say Accrued; nothing inside the well may (From line to footer), at 600, 390 or in the phone frame, in HTML or in the plain-text part. The L7 crawler is extended to rendered email HTML and text by R-01-T31. Template subjects, blocks and button labels are firm content: they live in `email_template_versions` rows (imported for Brightwater Hale by R-01-T22 through the import service), never in `copy.ts`, a constant or a migration. Every block is typed by a person or imported; no model text enters a template (ADR P-25 stays off).

## States

Fixture scenarios (R-01-T22, `fixtures/scenarios/POR-20.ts`, data in `fixtures/seed/email-templates.ts`), footed by the R-01-T22 scenario footing test (planned; Reminder open items 2 = POR-03 `open_count` = TAX-03 Intake 2). The screen is R-01-T25's.

12 artboards in the handoff (README letters a–l, canonical; i–l have no spec letter), 12 built here. Spec STATES letters map to built letters as spec b → e, c → f, d → g, e → h, f → i, g → k, h → l.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | grace-holloway (Grace Holloway, Firm Admin) | Mon Sep 14, 2026, 9:24 AM CT | E0 | `reminder`: v3 published, a v4 draft saved (pill "Draft changes · v4", row selected); preview `{source: draft, width: 600, sample_contact_id: claire-feld}` with Claire's 2 open client-visible requests; follow-up policy 7 days · max 4 · weekdays 9:00 recipient's time; sender domain `brightwaterhale.com` verified and `communications.firm_sender_domain` on for Brightwater Hale | fixture (T25) |
| b | grace-holloway | same | E0 | Data of a; Grace clicked the body (editor state, opened by the scenario step, not a prop): values render as variable chips, the editing bar shows, the list on the left inserts at the caret | fixture (T25) |
| c | grace-holloway | same | E0 | Data of a; `?w=390` (`POST …/preview {width: 390}`: same blocks reflowed, full-width button) | fixture (T25) |
| d | grace-holloway | same | E0 | Data of a; `?w=phone`: the v4 draft in a phone mail-client frame on the 470 × 900 board (subject, sender, 9:24 AM) | fixture (T25) |
| e | grace-holloway | same | E0 | `invitation` v3 published, no draft (Publish disabled, no Discard); sample `sam-ortiz` (third party, Keystone Retirement Services) with 9 delegated Northwind items; no Reminder schedule band | fixture (T25) |
| f | grace-holloway | same | E0 | `signature_request` v2 published, no draft; sample `owen-calder` (Ridgeline) with an engagement letter envelope due Sep 24, 2026 | fixture (T25) |
| g | grace-holloway | same | E0 | `deliverable_ready` v2 published, no draft; sample `meera-shah` with the released 2025 Ridgeline K-1 (no amount in the email) | fixture (T25) |
| h | grace-holloway | same | E0 | `confirmation_request` v1 published, no draft; sample respondent Rachel Imholt (Summit Trail Outfitters, accounts payable) for Granite Peak's confirmation C2, balance at June 30, 2026, single-use link expiring Oct 9, 2026 | fixture (T25) |
| i | grace-holloway | same | E0 | `reconnect_request` v1 published, no draft; sample `tess-moreno` (Copperleaf) whose American Express connection needs a new sign-in for the August 2026 close | fixture (T25) |
| j | grace-holloway | same | E0 | Data of a; "Send test…" opened the O3 sheet: Send to is Grace's own address (read-only), sample recipient Claire Feld selected | fixture (T25) |
| k | grace-holloway | **9:26 AM** | E0 + test send | `POST …/reminder/test-send {sample_contact_id: claire-feld}` succeeded (the sink holds one "[Test]" message to Grace); toast | fixture (T25) |
| l | grace-holloway | **9:27 AM** | E0 + publish | `POST …/reminder/publish` inserted v4 (published by Grace at Sep 14 9:27), retired v3, no draft: list pill "Published · v4", header pill "Published · v4 · Sep 14 by Grace Holloway", Publish disabled, no Discard | fixture (T25) |

Personas: `grace-holloway`, `claire-feld`, `sam-ortiz`, `meera-shah` and `tess-moreno` exist in the TS seed; `owen-calder` is added by R-01-T05 if absent; the respondent Rachel Imholt is a sample contact added by R-01-T22.

Non-artboard states (data conditions, never an `st` prop):

| State | Data condition | Rendering |
|---|---|---|
| Loading | `GET /v1/firm/email-templates` or `…/{key}` pending | F-05 ViewState skeleton rows in the structure pane and a skeleton card on the well |
| Error | a read fails | F-05 ViewState error row (C-20) with Retry |
| Unknown key | `$templateKey` is not registered for the firm: `404` | not-found |
| Flag off | `portal.settings_editor` false | read-only published values: list and preview of the published version; no inline edit, Send test…, Discard or Publish; schedule rows inert (copy key `flagOff.note`, string written by T25, see Open gaps) |
| Not allowed | Staff (Kevin Osei), any role without `email_template.read`, and the agent: the matrix denies (`403`) | C-20 not-allowed pane (a firm-level settings page, not a hidden record, so not-found does not apply) |
| Read only | `practice_leader`: `email_template.read` without `edit`, `test_send` or `publish` | the controls are absent from `allowed_actions` and not drawn |
| Stale draft | `PUT …/draft` or `POST …/publish` answers `409` on a stale `expected_version` | the draft reloads with the copy key `error.staleDraft` (string written by T25) |
| Lint finding | `POST …/preview` returns `findings[]`; test send or publish answers `422 template_lint_failed` | findings shown inline on their block as warnings; Publish stays disabled while any finding remains (R-01-T25); finding words keyed by code (`lint.<code>`, T23 owns the codes, T25 writes the words) |
| No published version | a key another epic registered and nobody published yet | pill copy key `pill.notPublished` (string written by T25); sends of that key fail closed (R-01-T19) |
| Sender fallback | sender domain not verified, or `communications.firm_sender_domain` off | From reads "Brightwater Hale" `<brightwaterhale@<neutral-mail-domain>>` with a Reply-To row (`meta.replyTo`, string written by T25); never an `accrued` address (DEC-59) |
| Fresh MFA | publish without a recent MFA | the shared step-up prompt (F-03), then the publish retries |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/firm/email-templates` | P-36 list: `items[{key, name, audience, used_by_label, used_by_screen?, published {version, published_at, published_by}?, draft {version, saved_at}?}]`, the designed six first (`group: designed`), registered keys after (`group: registered`) | `email_template.read` | `firm_admin`, `practice_leader`; every other firm role and the agent deny |
| read | `GET /v1/firm/email-templates/{key}` | `{key, variables[] (whitelist with sensitivity class), published {version, subject, preheader, blocks[], cta_label, content_sha256}?, draft {expected_version, subject, preheader, blocks[], cta_label}?, allowed_actions[]}` | `email_template.read` | as above; `allowed_actions` ⊆ `edit`, `test_send`, `publish` for `firm_admin` only |
| write | `PUT /v1/firm/email-templates/{key}/draft` | `{subject, preheader, blocks, cta_label, expected_version}`; `409` on stale; audits `email_template.draft_saved` | `email_template.edit` | `firm_admin` |
| write | `DELETE /v1/firm/email-templates/{key}/draft` | Discard; audits `email_template.draft_discarded` | `email_template.edit` | `firm_admin` |
| read | `POST /v1/firm/email-templates/{key}/preview` | `{source: draft\|published, width: 600\|390, sample_contact_id?}` → deterministic `{html, text, subject, from, reply_to?, findings[{code, block_id}]}` | `email_template.read` | `firm_admin`, `practice_leader` |
| write | `POST /v1/firm/email-templates/{key}/test-send` (`Idempotency-Key`) | `{sample_contact_id?}`; sends only to the acting admin with subject prefix "[Test]" (synthetic tenants: the sink); `422 template_lint_failed`; audits `email_template.test_sent` | `email_template.test_send` | `firm_admin` |
| write | `POST /v1/firm/email-templates/{key}/publish` (`Idempotency-Key`; fresh MFA) | insert-only version n+1 (`published`, `content_sha256`, `published_by/at`), retires n; `422 template_lint_failed`; audits `email_template.published`; outbox `email_template.published {key, version}` | `email_template.publish` (`mfa_recent: required`) | `firm_admin` |
| write | `POST /v1/firm/email-templates/import` | `{bundle, dry_run}`; onboarding only, no control on this screen (R-01-T22, T34) | `email_template.import` | `firm_admin` |
| read | `GET /v1/firm/follow-up-policy` | cadence, maximum, send-at, stop rules, `next_send_at` for the sample recipient (DEC-74) | `portal.settings.read` | `firm_admin`, `practice_leader` |
| write | `PUT /v1/firm/portal-settings/draft` | Reminder schedule edits join the portal-settings draft and publish from ADM-10 (see Open gaps) | `portal.settings.manage` | `firm_admin` |
| read | `GET /v1/firm/sending-domains` | domain status for the From line | `sending_domain.read` | `firm_admin`, `security_admin` |

Variables are the key's registered whitelist (R-01 §4.7): `{client_first_name}`, `{firm_name}`, `{work_item}`, `{open_items}` (request titles in client wording, at most 10, then "and n more"), `{due_date}`, `{portal_link}` (a 14-day secure link from P-08-T21, never a query string), `{staff_name}`, plus per-key `{inviter_name}`, `{organisation_name}`, `{scope_summary}`, `{document_title}`, `{deliverable_title}`, `{respondent_org}`, `{connection_name}`. None resolves to an amount, an account number or a TIN.

## Status
No status object from `docs/product/status-vocabulary.yaml` covers email template versions yet; DF-31 lists the additions ("template draft" with "Draft changes · vN"). Until they land the pills are:
- Published version: green-tint "Published · v3" (template `Published · v{n}`), and in the paper header after publish "Published · v4 · Sep 14 by Grace Holloway" (l).
- Draft over a published version: amber state tint "Draft changes · v4" (template `Draft changes · v{n}`).
- Toggles: on is `--green`. No red appears on this screen.
The `template_version` object in the vocabulary (Draft · Published · Deprecated) is the engagement-template object (KNW-07) and is not reused (see Open gaps).

## Copy
Copy keys live in `screens/POR-20/copy.ts`; every string below is verbatim from the built artboards (the built screen wins over spec.md where they differ). Template content (subjects, headlines, bodies, buttons, footers) is not copy: it is seeded as database rows by R-01-T22 and listed separately below.

Chrome and fixed strings:

| Key | String |
|---|---|
| `subbar.back` | "Firm settings" (with ChevronLeft) |
| `subbar.title` | "Email templates" |
| `subbar.context` | "Portal & client experience" |
| `structure.header` | "Portal › Email templates" |
| `band.templates` | "Templates" |
| `row.usedBy` | template `Used by {used_by_label}` ("Used by CLI-04 invites, prospect intake") |
| `pill.published` | "Published · v3" (template `Published · v{n}`) |
| `pill.draft` | "Draft changes · v4" (template `Draft changes · v{n}`) |
| `pill.publishedBy` | "Published · v4 · Sep 14 by Grace Holloway" (template `Published · v{n} · {date} by {person}`) |
| `band.schedule` | "Reminder schedule" (shown for `reminder` only) |
| `schedule.cadence` | "Cadence" · "Every 7 days until done" (template `Every {n} days until done`) |
| `schedule.max` | "Maximum reminders" · "4" |
| `schedule.sendAt` | "Send at" · "Weekdays · 9:00 AM recipient's time" |
| `schedule.stopWhenDone` | "Stop when the client marks the binder done" |
| `schedule.copyPreparer` | "Copy the assigned preparer" |
| `band.variables` | "Variables" |
| `band.rules` | "Rules" |
| `rules.body` | "Emails never include account numbers, SSNs, tax amounts or attachments. Everything sensitive stays in the portal." |
| `paper.width` | "600" · "390" |
| `paper.sendTest` | "Send test…" |
| `paper.discard` | "Discard" |
| `paper.publish` | "Publish v4" (template `Publish v{n}`); "Publish" when there is no draft (disabled) |
| `meta.from` / `meta.to` / `meta.subject` | "From" · "To" · "Subject" |
| `editing.bar` | "Editing · choose a variable on the left to insert it at the cursor" |
| `editing.done` | "Done" |
| `phone.back` | "Inbox" |
| `phone.toMe` | "to me" (as "clients@brightwaterhale.com · to me") |
| `testSheet.title` | "Send a test email" |
| `testSheet.sendTo` | "Send to" · "Email" |
| `testSheet.sample` | "Sample recipient" |
| `testSheet.note` | "The test fills in this person's details and goes only to you." |
| `testSheet.cancel` | "Cancel" |
| `testSheet.send` | "Send test" |
| `toast.testSent` | "Test sent to grace.holloway@brightwaterhale.com" (template `Test sent to {email}`) |
| `flagOff.note`, `error.staleDraft`, `pill.notPublished`, `meta.replyTo`, `band.registered`, `lint.<code>` | reserved; no handoff string exists, R-01-T25 writes them (see Open gaps) |

Registry labels (from `register_email_template`, shown in the list): Invitation / "CLI-04 invites, prospect intake" · Reminder / "Binders, close requests, PBC" · Signature request / "SIG-02 envelopes" · Deliverable ready / "Returns, K-1s, statements, reports" · Confirmation request / "AUD-14 · single-use link, no portal" · Reconnect request / "CLS-11 · expired connections". Variable chips read `{client_first_name}` `{firm_name}` `{work_item}` `{open_items}` `{due_date}` `{portal_link}` `{staff_name}`.

Send test… sample recipients (j; seed contacts, shown as rendered): "Claire Feld" / "Reminder · 2 open items for her 2025 tax return" · "Sam Ortiz" / "Invitation · Keystone Retirement Services" · "Owen Calder" / "Signature request · Ridgeline Property Partners, LP" · "Meera Shah" / "Deliverable ready · Ridgeline K-1 recipient" · "Summit Trail Outfitters" / "Confirmation request · Rachel Imholt, accounts payable" · "Tess Moreno" / "Reconnect request · Copperleaf Coffee Roasters, Inc.".

Seeded template content (database rows imported by R-01-T22; rendered with the sample's values):

| Artboard · key · version | From / To / Subject | Headline · body · button · closing line |
|---|---|---|
| a–d, j–l · `reminder` v4 draft | "Brightwater Hale <clients@brightwaterhale.com>" / "claire.feld@gmail.com" / "2 items still needed for your 2025 tax return" | "We still need 2 items" · "Hi Claire, we're working on your 2025 tax return. To keep it on track, please upload:" · items "Form 1095-C From Mercer Hill Health" and "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations" · "Drop the files in your portal and they'll be sorted for you." · button "Open your portal" · "Questions? Message Kevin Osei in your portal." |
| e · `invitation` v3 | same sender / "sam.ortiz@keystoneretirement.com" / "Brightwater Hale invited you to upload documents" | "You've been asked for 9 items" · "Hi Sam, Brightwater Hale LLP is auditing the Northwind Robotics 401(k) Plan and has asked Keystone Retirement Services for 9 items. Sign in to upload them securely." · button "Open requests" · "Questions? Message Marcus Delaney in your request room." |
| f · `signature_request` v2 | same sender / "owen.calder@ridgelinepp.com" / "Please sign: engagement letter — cost segregation and section 754 analysis" | "Ready for your signature" · "Hi Owen, please review and sign your engagement letter — cost segregation and section 754 analysis." · "Due September 24, 2026." · button "Review and sign" · "Questions? Message Daniel Reyes in your portal." |
| g · `deliverable_ready` v2 | same sender / "meera.shah@shahadvisory.com" / "Your 2025 K-1 from Ridgeline Property Partners, LP is ready" | "Ready to view" · "Hi Meera, your 2025 K-1 from Ridgeline Property Partners, LP is in your portal. Sign in to view or download it." · button "View your K-1" · "Questions? Message Olivia Brandt in your portal." |
| h · `confirmation_request` v1 | "Brightwater Hale LLP, auditors of Granite Peak Outdoor Supply, Inc. <clients@brightwaterhale.com>" / "r.imholt@example.com" / "Confirmation request — balance at June 30, 2026 (reference C2)" | "Please confirm a balance" · "Hi Rachel, as auditors of Granite Peak Outdoor Supply, Inc., we're asking Summit Trail Outfitters to confirm the balance it owed Granite Peak at June 30, 2026. Please respond directly to us using the secure link." · button "Respond securely" · "This link works once and expires on October 9, 2026. To check it's genuine, call Brightwater Hale using the number on our website." |
| i · `reconnect_request` v1 | same sender / "tess@copperleafcoffee.com" / "Please reconnect American Express for your monthly close" | "Reconnect American Express" · "Hi Tess, American Express asks you to sign in again every 90 days, so new card transactions aren't reaching us for your August 2026 close. Reconnecting in your portal restarts the feed." · button "Reconnect" · "Questions? Message Raj Malhotra in your portal." |

Email footers (address from branding, reason line from the key): "Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL · You're receiving this because you're a client of Brightwater Hale. We never include account numbers or tax amounts in email. Email preferences" (a–d, f, g, i, j–l); e: "… You're receiving this because Brightwater Hale asked Keystone Retirement Services for documents. We never include account numbers or tax amounts in email. This link expires in 14 days. Email preferences" (DEC-35); h: "… You're receiving this because Granite Peak Outdoor Supply, Inc. authorized us to confirm a balance with you. We never include account numbers or tax amounts in email." (no preferences link). Every email carries the firm mark and "Brightwater Hale" above a hair rule.

Accessibility labels (R-01 §5.6): variable chips are buttons named "client first name, variable" (pattern `{words}, variable`); the preview offers its plain-text part on demand; the O3 sheet is labelled "Send a test email".

Copy bans inside the well (R-01 §5.7, glossary rows from R-01-T04): "Accrued" (the optional footer is off), the agent or "AI", confidence, firm status words, materiality, an amount, an account number, a TIN or SSN, an attachment, a second button.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "‹ Firm settings", subbar context "Portal & client experience" | ADM-10 `to.ADM10()` | planned (R-01-T28) |
| Invitation row "Used by CLI-04 invites, prospect intake" | CLI-04 | planned |
| Signature request row "Used by SIG-02 envelopes" (the designed link opens the hub) | SIG-01 | planned (N-02) |
| Deliverable ready row "Used by Returns, K-1s, statements, reports" | TXP-12 | planned |
| Confirmation request row "Used by AUD-14 · single-use link, no portal" | AUD-14 | planned (A-08) |
| Reconnect request row "Used by CLS-11 · expired connections" | CLS-11 | planned (C-01) |
| Reminder row "Used by Binders, close requests, PBC" | none (no designed target) | — |
| Template rows | the same screen with another `$templateKey` | in-screen |
| "600" · "390"; phone frame | the same screen with `?w=` | in-screen |
| "Send test…" | O3 sheet; `POST …/test-send` | in-screen |
| "Discard" · "Publish v4" | `DELETE …/draft` · `POST …/publish` | in-screen |
| Preview button "Open your portal" (Reminder) | POR-01 sign-in, then POR-03 (the open items) or POR-02 | preview-only; POR-01 fixture (P-08-T09), POR-02 fixture (P-08-T15), POR-03 planned (R-01-T06) |
| Preview button "Open requests" (Invitation) | POR-01 sign-in, then POR-14 | preview-only; POR-14 planned (R-01-T14) |
| Preview button "Review and sign" (Signature request) | POR-06 | preview-only; planned (N-02) |
| Preview button "View your K-1" (Deliverable ready) | POR-09 | preview-only; planned (R-02) |
| Preview button "Respond securely" (Confirmation request; single-use link, no portal sign-in) | POR-17 | preview-only; planned (A-08) |
| Preview button "Reconnect" (Reconnect request) | POR-16 | preview-only; planned (A-02) |

Inbound: ADM-10 ("Edit in POR-20 ›", "Preview at 600 and 390 px in POR-20.", and the J16 path ADM-10 → POR-20), CLI-04, SIG-02, TXP-12, AUD-14 and CLS-11 (each sends one key). Preview buttons do not navigate in production: the firm app holds no portal session and the portal is another origin (DEC-59), so the button shows its target on hover; in fixture builds it opens the target's artboard ("Not built yet" when `planned`). All targets are manifest IDs that `link-contract.test.ts` knows, and every designed link of POR-20 in `handoff-links.json` (ADM-10, CLI-04, SIG-01, TXP-12, AUD-14, CLS-11) is named above.

## Acceptance
- POR-20 acceptance: T10 geometry: a 470 structure pane and an 896 paper pane with a centred 600 px email card on the `#F8F8F6` well, in the SHL-01 shell with the firm pill pressed.
- POR-20 acceptance: six templates, each with exactly one dark button whose destination is a portal screen (POR-01 / POR-14 / POR-06 / POR-09 / POR-17 / POR-16).
- POR-20 acceptance: the Reminder lists exactly Claire Feld's 2 open items (= POR-03 `open_count` = TAX-03 Intake 2); the cadence reads every 7 days.
- POR-20 acceptance: no amount, account number or SSN in any rendered email, HTML or text; the confirmation email tells the respondent to verify the firm independently.
- POR-20 acceptance: client emails show only Brightwater Hale; nothing inside the well contains "Accrued" at 600, 390 or in the phone frame.
- POR-20 acceptance (R-01 Story 7.1): the list shows the designed six with their Used-by links and pills "Published · v3" and "Draft changes · v4", the well previews v4 with Claire's two items, and a second band lists keys other epics register.
- POR-20 acceptance (Story 7.1): inline editing shows neutral chips with the variable name on hover and inserts any whitelisted variable at the caret; a stale `expected_version` answers 409 and nothing is lost silently.
- POR-20 acceptance (Story 7.1): 390 and the phone frame render the same deterministic blocks reflowed with a full-width button, with a plain-text part.
- POR-20 acceptance (Story 7.2): a draft with "$3,200", a TIN-shaped number, an account number, an attachment, a second button, an unregistered variable, a foreign link or the word Accrued shows each finding on its block, and test send and publish answer 422 `template_lint_failed`; Publish stays disabled while a finding remains.
- POR-20 acceptance (Story 7.3): Send test… goes only to the acting admin with "[Test]" in the subject and audits `email_template.test_sent`; no other address is accepted.
- POR-20 acceptance (Story 7.3): Publish with fresh MFA inserts v4, retires v3, shows "Published · v4 · Sep 14 by Grace Holloway" with Publish disabled; later reminders use v4 and sent messages keep their `template_version_id`.
- POR-20 acceptance (Story 7.3): Staff and the agent principal are denied edit, test send and publish (INV-1).

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Reminder open items 2 | = POR-03 a `open_count` 2 = TAX-03 Intake 2 = POR-02 "Upload 2 documents" (Form 1095-C; the two estimated-payment confirmations) | R-01-T22 scenario footing test (planned) |
| Templates | 6 designed keys: Invitation v3, Reminder v3 + draft v4, Signature request v2, Deliverable ready v2, Confirmation request v1, Reconnect request v1 = ADM-10 "6 of 6 published · 1 with draft changes" | same |
| After l | Reminder v4 published Sep 14 9:27 by Grace Holloway; v3 retired and still readable | same; R-01-T30 version immutability |
| Cadence | every 7 days, at most 4, weekdays 9:00 AM recipient's time (DEC-74); last reminder Mon Sep 14 9:00 AM → next Mon Sep 21; at 5 days Sat Sep 19 moves to Mon Sep 21 (ADM-10 b) | R-01-T24 `next_send_at` test |
| Invitation | 9 Northwind items asked of Keystone (= POR-14 a "9") | R-01-T05 footing (Keystone 4 of 9) |
| Signature request | due Sep 24, 2026 | R-01-T22 footing |
| Confirmation request | balance at June 30, 2026, reference C2; link single use, expires Oct 9, 2026 (= AUD-14 / POR-17) | same |
| Test send | k at 9:26 AM to grace.holloway@brightwaterhale.com only | scenario test k |

## AVOID
Each becomes a test in `POR-20.test.tsx` ("POR-20 avoid: …"): gradients in product UI, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, images or banners in emails, more than one button in an email, tax amounts or account numbers in email, the Accrued name or logo in client emails, purple for variables (purple is only for source tracing).

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| — | i, j, k and l have no spec letter (added during the build) and are canonical; spec letters b–h map to built e–i, k and l | Handoff README rule: the built screen wins | R-01 §2.1 |
| F-06 | The well renders through R-01's interim `EmailPreview`; F-06-T16 re-homes it onto T10e (`DocumentOnWell variant="email"`) in S18. If F-06's cut tier keeps the interim, N-04 re-homes it | The T10 kit lands in F-06 (S17–S18), after this screen (S11) | R-01 §2.1, §5.3; F-06 cut tier |
| DF-40 | The list shows every registered firm-editable key: the designed six first, then keys other epics register (P-06's Request and Return, `request_sent` / `request_returned`; DF-40's governance letter, POR-18/21/22/23 keys) in a second GroupBand | DF-40 keys register through R-01's slot in their own epics, as database content | chapter 09 DF-40; R-01 §4.7 |
| DEC-35 | The Invitation footer reads "This link expires in 14 days." and the link is single use | 14-day single-use invitation links | decision-log DEC-35 |
| DEC-59 | From is the firm domain only once `brightwaterhale.com` is verified and `communications.firm_sender_domain` is on; otherwise "Brightwater Hale" `<brightwaterhale@<neutral-mail-domain>>` with Reply-To the firm address; never an `accrued` address | White-label portal, per-firm DKIM | decision-log DEC-59; ADR-163 |
| ADR P-25 | No model-drafted text in any template; every block is typed by a person or imported | ADR P-25 stays off | R-01 §0.1 |
| DEC-74 | The Reminder schedule is the firm follow-up policy (one policy, shared with ADM-10); a person approves the template once; reminders built from it may go on a system schedule only behind `follow_ups.scheduled_send` | Follow-ups and reminder cadence | decision-log DEC-74 |
| DEC-58(d) | No change on this screen: email plus the Home list replace a portal bell, so these keys are how the client is reached | No portal bell | decision-log DEC-58 |
| DEC-58 a/c/e/f/g | Not on this screen (POR-03, POR-04) | — | R-01 §2.1 |
| DF-03 | c (390) and d (phone frame) are the 390 renderings for this screen; no other 390 layout (the screen itself is firm-side desktop) | DF-03 lists the POR-20 previews | chapter 09 DF-03 |
| DF-15 | Not on this screen | — | R-01 §2.1 |
| — | Preview buttons do not navigate in production (shown with their target); they open their artboard in fixture builds | Two origins; the firm app holds no portal session | DEC-59; this contract |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a–c, e–l | C (threshold 0.20, maxDiffPixelRatio 3 %) | a 3.36 · b 3.41 · c 3.90 · e 2.75 · f 2.67 · g 2.49 · h 3.00 · i 2.62 · j 69.47 · k 4.26 · l 3.05 (2026-10-28) | the gallery draws the 1400 × 860 window without SHL-01's chrome (`[data-window]`), which most of the over-3 % is; b, j and k are reached by a click (the editor, the Send test sheet, a lint state) and the gallery opens each on its template, so j is the Send test sheet missing; reported from S11; locked at R-01 exit (S18) after F-06-T16 re-homes the well (R-01-T31); the second GroupBand of registered keys is masked |
| d | C | not run (deviation) | the 470 × 900 board: its manifest entry is report-only until the gallery draws d's phone board alone |
| host | D | — | toolbar 46, subbar 46–88, panes from y98, structure 470, paper 896, pane header 46 with a 14.5/500 title, list rows 52, bands 31, ValueRows 34, variable chips 24, email card 600 r12 padding 28 32, button 40 r999 (390: full width, 44), toast 36 |

Tier B for SHL-01 is F-05's; T10 is F-06's.

## Open gaps
- **i viewer.** The README viewer column reads Tess Moreno for i; she is the sample recipient. The viewer is `grace-holloway` (R-01 §5.4).
- **Signature request link.** The row text says "SIG-02 envelopes" while the designed link opens SIG-01 (`handoff-links.json`, R-01 Story 7.1). The link follows the graph; the label is the registry's.
- **Variable chips per key.** The built e–i show the seven general chips for every key; ADM-10 e shows the Reconnect key's own set (`{client_first_name}` `{firm_name}` `{portal_link}` `{connection_name}`). The chips come from the key's registered whitelist (`GET …/{key}`); where that differs from the built e–i, R-01-T31 masks the Variables band for those artboards.
- **Reminder schedule writes.** POR-20 and ADM-10 show one policy. Decided here: schedule edits on POR-20 save into the portal-settings draft (`PUT /v1/firm/portal-settings/draft`) and publish from ADM-10; "Publish v4" publishes the template only. R-01-T25 and T26 confirm before building.
- **"Copy the assigned preparer".** Shown on POR-20 only; neither DEC-74 nor ADM-10 has it. R-01-T24 decides whether the policy carries it; until then the row is fixture-only.
- **Reconnect request v1 conflict.** POR-20 i renders v1 as "Please reconnect American Express for your monthly close"; ADM-10 e shows v1 raw as "Please reconnect your accounting system" with a different body. One v1 is seeded: decided here as POR-20 i's (the template screen of record, Story 7.1); ADM-10 e's drawer shows the same row and its content region is masked in parity. To confirm with AY before R-01-T22.
- **Per-key sender display name.** h's From reads "Brightwater Hale LLP, auditors of Granite Peak Outdoor Supply, Inc."; the draft shape has no sender field. R-01-T19 adds a per-key display-name block or composes it from `{respondent_org}`; recorded for T16's contract.
- **"Email preferences" link.** Story 7.2's lint allows only `{portal_link}` and the branding help and privacy links; the footer link has no named target. R-01-T23 decides (a branding link, or the lint allows it); no manifest target is named until then.
- **Strings with no handoff copy.** Flag-off note, stale draft (409), lint finding words (422), error row, the second band title, Reply-To row and the not-published pill: keys reserved above; R-01-T25 writes them inside the copy bans and records them here.
- **Status vocabulary.** "Published · vN" and "Draft changes · vN" for email templates are DF-31 additions not yet in `status-vocabulary.yaml`; they must land before R-01-T25. The existing `template_version` object belongs to engagement templates.
- **Request title casing.** The built well reads "Form 1095-C From Mercer Hill Health" (capital F), as the seed's request title does (`fixtures/seed/requests.ts`); the ADM-10 spec's "from" is not followed.
