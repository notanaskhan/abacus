# C16 v1.1 · Firm email templates, sending domains and the follow-up policy

| Field | Value |
|---|---|
| Register row | C16 in `docs/contracts/README.md` (v1.1, additive; v1 is `notifications.md`, frozen) |
| Version | v1.1 |
| Status | stub (R-01-T16, 2026-10-26); list, read, draft, publish and `send_templated` live (R-01-T19, 2026-10-27; DEC-449); preview, test send and import live (R-01-T23, 2026-10-27; DEC-549, DEC-560 to DEC-562); the follow-up policy read live (R-01-T24, 2026-10-27; DEC-563 to DEC-566); sending domains still 501 (R-01-T27) |
| Provider epic | R-01 (N the email half, AY the screens); T19 drafts and publish, T23 preview, lint, test send and import, T24 follow-up policy, T27 sending domains |
| Consumers | POR-20, ADM-10 (R-01-T25, T28); P-06 (`request_sent`, `request_returned`, `reminder`); P-08 (`portal.sign_in_code`, platform-locked, same renderer); N-02 (`signature_request`); A-02 (`reconnect_request`); A-08 (`confirmation_request`); R-02, A-07, T-02 (`deliverable_ready`); R-03, X-01, X-03, A-09 (DF-40 keys); N-03 (sender domains); Q-04 (import) |
| Freeze sprint | at the R-01 S12 review (with T19) |
| Flag | `portal.settings_editor` (template writes), `communications.firm_sender_domain` (sending-domain writes and the From selection), `follow_ups.scheduled_send` (system-scheduled reminders); all default off, expire 2027-04-21 |
| Spec | `docs/specs/SPEC-345-c16-v1-1-email-templates-portal-settings.md` |
| ADRs | ADR-005, ADR-031, ADR-139, ADR-163; DEC-59, DEC-74, DEC-35; ADR P-25 (off) |

## 1. Purpose
Consumers can rely on one slot to register a firm-editable template key, one function to send it (`send_templated`) with four refusal reasons, a variable whitelist that can never carry an amount, an account number or a TIN, and the POR-20 and ADM-10 shapes for template drafts, previews, test sends, publishing and the onboarding import, sending domains and the firm's follow-up policy. Template text is content: it arrives through the editor or the import, never through code or a migration.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| List | `GET /v1/firm/email-templates` | `email_template.read` | firm admin, practice leader | denied |
| Read one | `GET /v1/firm/email-templates/{key}` | `email_template.read` | as list | denied |
| Save draft | `PUT /v1/firm/email-templates/{key}/draft` | `email_template.edit` | firm admin | denied |
| Discard draft | `DELETE /v1/firm/email-templates/{key}/draft` | `email_template.edit` | firm admin | denied |
| Preview | `POST /v1/firm/email-templates/{key}/preview` | `email_template.read` | firm admin, practice leader | denied |
| Test send (`Idempotency-Key`, 202) | `POST /v1/firm/email-templates/{key}/test-send` | `email_template.test_send` | firm admin; fresh MFA, onshore; to their own address only | denied |
| Publish (`Idempotency-Key`, 201) | `POST /v1/firm/email-templates/{key}/publish` | `email_template.publish` | firm admin; fresh MFA | denied |
| Import | `POST /v1/firm/email-templates/import` | `email_template.import` | firm admin; fresh MFA | denied |
| Sending domains | `GET /v1/firm/sending-domains` | `sending_domain.read` | firm admin, security admin | denied |
| Add (`Idempotency-Key`, 201) | `POST /v1/firm/sending-domains` | `sending_domain.manage` | firm admin, security admin; fresh MFA | denied |
| Check | `POST /v1/firm/sending-domains/{domain_id}/check` | `sending_domain.manage` | as add | denied |
| Revoke | `DELETE /v1/firm/sending-domains/{domain_id}` | `sending_domain.manage` | as add | denied |
| Follow-up policy and next send | `GET /v1/firm/follow-up-policy?sample_contact_id=` | `portal_settings.read` | firm admin, practice leader | denied |

Flags: template writes 404 with `portal.settings_editor` off; sending-domain writes 404 with `communications.firm_sender_domain` off; reads and the import are never gated (off, the screens show published values read-only and `allowed_actions` is empty). Every route answers 501 `not_implemented` until its task; list, read, draft save and discard and publish are live (R-01-T19), preview, test send and import (R-01-T23) and the follow-up policy (R-01-T24): they authorise first, then check the flag (writes), then the key (404 for a key that is not registered firm-editable). Only the sending-domain routes still answer 501. Policy edits are saved through the portal-settings draft (`portal-settings.md`), so this contract only reads the policy.

### Module interface (`communications.api`)
- `register_email_template(key, audience, variables, cta_targets, used_by, *, firm_editable) -> EmailTemplateRegistration`: once per key at import time; variables from the whitelist only; at most one call-to-action target per audience; `used_by` names screen ids; a `staff` template is never firm-editable. `registered_templates()` lists them.
- `send_templated(ctx: AuthContext | SystemSendContext, key, recipient: RecipientRef, variables, *, scope: SendScope, idempotency_key) -> SendOutcome` (DEC-379): the caller's own context, never an asserted actor. For a person it authorises `message.send` on `scope.engagement_id` inside (independence, G2 on attest clients, walls; a refusal raises as `authorise` does), runs `lint_values` on the filled values and `check_scope` (ADR-065) on the rendered text. `SystemSendContext` is only a scheduled reminder (`reason: scheduled_follow_up`, the `reminder` key, its published version, `follow_ups.scheduled_send` on); never an agent. It queues one message or records it `blocked` with a `SendRefusal`: `template_missing` (no published version), `template_lint_failed` (text or values), `out_of_scope` (names another client, entity, account or amount; communications' `OutOfScope` check), `firm_not_client_facing` (the client-mail gate before the firm's M10 flip; staff recipients unaffected; synthetic firms always deliver to the sink), `suppressed` (a bounce or complaint). Built by R-01-T19 (DEC-449): the version in use is the firm's published one, else the platform default; the message records its `template_version_id` and `kind`, its body is the text part with the secure link removed, its id derives from the idempotency key (a retry sends nothing again), and delivery follows the commit. A recipient other than a `user` has no address resolver yet and is recorded `blocked` `suppressed`. A `user` recipient the engagement does not concern (not on its team, no client grant covering it) is refused 404 before anything is recorded (DEC-449). The button opens only the portal; `{portal_link}` never appears in text, and firm text carries no link, domain or address (`foreign_link`). `firm_not_client_facing` waits for R-01-T27 and the policy's mode for R-01-T24. The system path refuses (`Forbidden`) unless the reason is the scheduled reminder, the key is `reminder`, `follow_ups.scheduled_send` is on and the version in use is one the firm published (its publisher, still a member, is the message's author).
- `lint_values(values) -> ValueFinding[]` (DEC-379): the amount, TIN-shape and account-number rules over every filled value (each line of `open_items`). Template text is safe by the closed kinds; values are client-written (a `document_title` "W-2 912-34-5678 $84,210.pdf"), so preview shows the findings and test send and send refuse `template_lint_failed` naming the code and the variable, never the value. A masked last four ("••4436") counts as an account number; `connection_name` is the catalogue name ("American Express"), never the masked label. Nothing is masked into a near-miss: fail closed.
- `viewer_scoped(items, viewer_can_read, *, contact_visible) -> PreviewSelection` (DEC-379): what a preview or test send may show of a real `sample_contact_id`. The preview actions grant no client content: the contact must be visible to the viewer, each item (request, binder, work item) is kept only if the viewer could read it themselves (`engagement.read` and the item's read action under `visible()`, walls, independence), dropped items leave no count, and with nothing left the sample client renders. A firm admin walled off Copperleaf previews Tess Moreno as the sample client.
- `scheduled_send_enabled(tenant)`: whether a `send_on_schedule` policy may send by itself (`follow_ups.scheduled_send`).
- `TEMPLATE_VARIABLES`: the whitelist below; `FollowUpPolicyFields` and `NextSendOut` for the portal-settings draft.

## 3. Models
Code: `backend/src/abacus/modules/communications/template_registry.py` (slot) and `templates_contract.py` (routes).

**Variables** (R-01 §4.7), each `{name, kind, classification, block}`:

| Variable | Kind | Class |
|---|---|---|
| `client_first_name` | person_name | confidential |
| `firm_name` | organisation_name | public |
| `work_item` | title | confidential |
| `open_items` (block: request titles in client wording, ≤ 10 then "and n more") | item_list | confidential |
| `due_date` | date | internal |
| `portal_link` (a 14-day secure link, P-08-T21; never a query string) | secure_link | confidential |
| `staff_name` | person_name | internal |
| `inviter_name` | person_name | confidential |
| `organisation_name` | organisation_name | confidential |
| `scope_summary` | summary | confidential |
| `document_title`, `deliverable_title`, `connection_name` | title | confidential |
| `respondent_org` | organisation_name | confidential |

The kind list is closed (`person_name`, `organisation_name`, `title`, `item_list`, `date`, `secure_link`, `summary`): there is no amount, account-number or TIN kind, and no variable is Restricted.

- `EmailTemplateListOut {items: EmailTemplateRowOut[]}`; a row `{key, name, group: designed | registered, audience[], used_by_label, used_by_screen?, published? {version, published_at, published_by}, draft? {version, saved_at}}`.
- `EmailTemplateOut {key, name, audience[], firm_editable, variables: TemplateVariableOut[], published?: EmailTemplateVersionOut, draft?: EmailTemplateDraftOut, allowed_actions: (edit | test_send | publish)[]}`.
- `EmailTemplateVersionOut {version, subject, preheader, blocks: TemplateBlock[], cta_label?, cta_target?, content_sha256, published_at, published_by?}` (`published_by` is null for a platform default; the same on the list row's `published`); `EmailTemplateDraftOut {expected_version, base_version?, subject, preheader, blocks, cta_label?, cta_target?, saved_at, saved_by}`.
- `TemplateBlock {id, kind: heading | paragraph | item_list | note | footer, text ≤ 2000 (confidential)}`; `cta_target ∈ portal_home, documents, request, room, sign, deliverables, confirm, connections`.
- `EmailTemplateDraftIn {subject, preheader, blocks ≤ 40, cta_label?, cta_target?, expected_version}`.
- `EmailPreviewIn {source: draft | published, width: 600 | 390, sample_contact_id?}` → `EmailPreviewOut {subject, html, text, from_display, from_address, reply_to?, findings: LintFindingOut[]}` (deterministic).
- `LintFindingOut {code, block_id?, variable?}` (`variable` set for a finding on a filled value); codes `amount`, `tin_shape`, `account_number`, `attachment`, `second_button`, `unregistered_variable`, `foreign_link`, `platform_name` (the word "Accrued"), `banned_word` (R-01-T23, DEC-562: the glossary's client-email bans and `scope-guards.yaml`'s banned terms). Identifier-only: never the offending text.
- `EmailTestSendIn {sample_contact_id?}` (no other field: an address in the body is 422) → `EmailTestSendOut {message_id, sent_to (the admin's own account address, from the session), subject ("[Test] …")}`. The draft if there is one, else the version in use; no `messages` row (DEC-549).
- `FirmEmailTemplateImportIn {bundle: EmailTemplateBundleEntryIn[] 1–50, dry_run = true}` → `FirmEmailTemplateImportOut {dry_run, results: {key, change: add | update | unchanged | refused, findings[]}[]}`. C16 v1's staff `EmailTemplateImportIn` is a different, frozen model.
- `SendingDomainOut {id, domain, from_local_part, mail_from_domain, status: pending_dns | verified | failed | revoked, records: {type: CNAME | MX | TXT, name, value, status}[], failure_reason?, requested_at, verified_at?, last_checked_at?}`; `SendingDomainIn {domain, from_local_part = "clients"}`.
- `FollowUpPolicyOut {policy: FollowUpPolicyFields, version, next_send?: NextSendOut}`; `FollowUpPolicyFields {cadence_days 1–30 = 7, max_reminders 1–4 = 4, send_local_time "09:00", weekdays_only, stop_on_binder_done, notify_preparer_after_max, cc_assigned_preparer, mode: draft_for_person | send_on_schedule}`; `NextSendOut {sample_contact_id?, last_sent_at?, next_send_at, shifted_from?}`.

## 4. Status words
Template pills "Published · v{n}" and "Draft changes · v{n}" and the sender-domain words "Pending DNS" and "Verified" are DF-31 additions, not yet in `docs/product/status-vocabulary.yaml`; they land before R-01-T25 and T28 (`docs/screens/POR-20.md`, `ADM-10.md`). The engagement-template object `template_version` is not reused. Until then `SendingDomainOut.status` is a recorded finding in the status-vocabulary acceptance suite.

## 5. Human-only actions
Every action here is denied to the agent and the system at the matrix (INV-1). Stubs check the flag before anything else, as every stub on main does; the implementing tasks authorise first (a wall answers 404 before the flag or any read). A model never writes a template (ADR P-25 off). The system sends a Reminder only from a published version, behind `follow_ups.scheduled_send`, attributed "Reminder v4 published by Grace Holloway" (INV-5).

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not_found"}` | flag off (writes); an unknown key; a preview of a draft or version that isn't there; a sample contact that relates to no engagement on the viewer's team, or is unknown (DEC-560) |
| 409 | `{"detail": "stale_version"}` | a draft save over a newer draft; a publish with no draft, over a newer draft, or of a draft based on a version that is no longer in use |
| 409 | `{"detail": "sending_domain_exists"}` | a second domain while one is pending or verified |
| 422 | `{"detail": "template_lint_failed", "facts": {"count": n, "finding_0": "amount:b2", …}}` | test send or publish of a draft with findings, or an applied import with a refused entry (at most 20 `finding_<n>`, each `code:where`, `where` a block id or `subject`, `preheader`, `cta_label`, `var:<variable>` for a filled value, `<key>.<where>` for an import entry; identifier-only facts, ADR-139) |
| 422 | `{"detail": "template_invalid"}` | a draft whose call to action the key does not register, a label without a target, a repeated block id, a line break in the subject or a stray brace |
| 501 | `{"detail": "not_implemented"}` | until the implementing task |

`send_templated` never raises a refusal; it records `blocked` with the reason.

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `email_template.draft_saved`, `.draft_discarded` | draft writes | key, draft version |
| `email_template.test_sent` | test send | key, message id |
| `email_template.published` | publish | key, version, content SHA-256 |
| `email_template.imported` | import (not dry runs) | keys, changes |
| `sending_domain.created`, `.verified`, `.failed`, `.revoked` | domain lifecycle | domain id, status |
| `message.blocked` | a refusal | message id, reason |
| `follow_up.scheduled_sent` | a system reminder | template key and version, its publisher |

Outbox: `email_template.published {key, version}`, `sending_domain.status_changed {domain_id, status}`, `message.delivery_status_changed {message_id, status}`.

## 8. Example payloads
Grace Holloway (Firm Admin), Brightwater Hale, Mon Sep 14, 2026, 9:24 AM CT (POR-20 a): `reminder` v3 published, v4 draft saved, previewed for Claire Feld with her 2 open requests; policy every 7 days, at most 4, weekdays 9:00 AM recipient's time; next send after Mon Sep 14 9:00 AM is Mon Sep 21 (at 5 days, Sat Sep 19 shifts to Mon Sep 21). At 9:26 AM a test send went to Grace only; at 9:27 AM v4 was published.

```json
GET /v1/firm/follow-up-policy?sample_contact_id={claire}
{"policy": {"cadence_days": 7, "max_reminders": 4, "send_local_time": "09:00",
            "weekdays_only": true, "stop_on_binder_done": true,
            "notify_preparer_after_max": true, "cc_assigned_preparer": false,
            "mode": "draft_for_person"},
 "version": 1,
 "next_send": {"sample_contact_id": "…", "last_sent_at": "2026-09-14T14:00:00Z",
               "next_send_at": "2026-09-21T14:00:00Z", "shifted_from": null}}
```

## 9. Consumer contract tests
`backend/tests/contracts/c16_notifications/test_c16_v1_1_stub.py` (provider: one action per route, flags, Idempotency-Key, fresh MFA, classification, the slot and `send_templated`); `backend/tests/contracts/c16_notifications/test_c16_v1_1_consumers.py` (R-01-T17 on behalf of R-01, P-06, N-02, A-02, A-08 and R-02: keys and variables, the whitelist's safety, refusal reasons, lint findings, settings draft and publish, read-only preview). The POR-20 and ADM-10 TypeScript fixture assertions arrive with R-01-T22.

## 10. Versioning
v1.1 is additive to C16 v1 (frozen 2026-10-23): new routes and models only. Breaking changes ship as v2 with one sprint of overlap.

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1.1 | (planned at the R-01 S12 review) | | stub R-01-T16; T19 built list, read, drafts, publish and `send_templated` |

## 11. Open points
Decided in DEC-378; the security review's preview scoping, `send_templated` signature, value lint and test-send conditions in DEC-379; T23's test send, sample contacts, import and lint in DEC-549, DEC-560 to DEC-562 (the "Email preferences" link is the branding footer's, outside the template; a "••" last four stays an account number, fail closed); T24's policy, limit and scheduled send in DEC-563 to DEC-566. Open, from the screen contracts: the per-key sender display name (POR-20 h).
