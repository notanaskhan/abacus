# C16 v1.1 · Portal settings and the read-only preview

| Field | Value |
|---|---|
| Register row | C16 in `docs/contracts/README.md` (v1.1, additive) |
| Version | v1.1 |
| Status | stub (R-01-T16, 2026-10-26) |
| Provider epic | R-01 (T26 settings and preview; T24 the policy inside them) |
| Consumers | ADM-10 (R-01-T28); POR-20's Reminder schedule (saved here); P-08 branding (`set_branding`, `set_logo`); R-01-T24 (the published policy); R-02, A-07 (the published client experience) |
| Freeze sprint | at the R-01 S12 review (with T26) |
| Flag | `portal.settings_editor` (draft, publish, logo); default off, expires 2027-04-21 |
| Spec | `docs/specs/SPEC-345-c16-v1-1-email-templates-portal-settings.md` |
| ADRs | ADR-155 (slots, not theming), ADR-163 (white label), ADR-024; DEC-20, DEC-59, DEC-74 |

## 1. Purpose
Consumers can rely on one versioned set of portal settings per firm (brand slots, client-experience toggles and the follow-up policy) with a draft and an insert-only publish, and on a read-only preview of POR-02 as one visible contact (or a sample client) would see it.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Read | `GET /v1/firm/portal-settings` | `portal_settings.read` | firm admin, practice leader | denied |
| Save draft | `PUT /v1/firm/portal-settings/draft` | `portal_settings.manage` | firm admin; fresh MFA | denied |
| Discard draft | `DELETE /v1/firm/portal-settings/draft` | `portal_settings.manage` | as save | denied |
| Publish (`Idempotency-Key`, 201) | `POST /v1/firm/portal-settings/publish` | `portal_settings.manage` | as save | denied |
| Logo (raw body) | `POST /v1/firm/portal-settings/logo` | `portal_settings.manage` | as save | denied |
| Preview | `GET /v1/firm/portal-settings/preview?as=&device=desktop\|phone&source=draft\|published` | `portal.preview` | firm admin | denied |

The plan's `portal.settings.read` and `portal.settings.manage` are spelt `portal_settings.*` (DEC-139: an action has one dot). The plan's `preview_target_visible` condition is the service's check, not a matrix condition: a contact outside the viewer's `visible()` answers 404 and is never offered (DEC-20). Writes 404 with `portal.settings_editor` off; reads and the preview are not gated. Every route answers 501 until R-01-T26.

## 3. Models
Code: `backend/src/abacus/modules/portal/settings_contract.py`; the policy fields are `communications.api.FollowUpPolicyFields`.

- `PortalSettingsOut {published?: PortalSettingsVersionOut, draft?: PortalSettingsDraftOut, next_reminder?: NextSendOut, allowed_actions: (edit | publish | preview)[]}`.
- `PortalSettingsVersionOut {version, brand: PortalBrandOut, client_experience, follow_up_policy, content_sha256, published_at, published_by}` (insert-only).
- `PortalSettingsDraftOut {expected_version, base_version?, brand: PortalBrandFields, client_experience, follow_up_policy, has_new_logo, saved_at, saved_by}`.
- `PortalSettingsDraftIn {brand: PortalBrandFields, client_experience: ClientExperienceFields, follow_up_policy: FollowUpPolicyFields, expected_version}`.
- `PortalBrandFields {portal_name, sender_display_name, secured_footer = false}`; `PortalBrandOut` adds `accent: "espresso"` (fixed), `portal_host` (read-only, the neutral host) and `logo_url?`.
- `ClientExperienceFields {allow_upload_something_else = false (until N-01, R-01-T33), phone_capture = true, show_team_card = true, show_progress_per_item = true, support_contact_user_id?}`.
- `PortalLogoOut {logo_sha256, expected_version}`.
- `PortalPreviewOut {read_only: true, device, contact_id? (null: the sample client), sample, source, brand, home: PortalHomeOut}`: P-08's POR-02 projection in preview mode, no session, no `allowed_actions` reachable.

## 4. Status words
Inside the preview, POR-02's own client words. Settings carry no status object.

## 5. Human-only actions
All six routes deny the agent and the system. Preview never widens access (ADR-024): it reads only what the viewer may read.

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not_found"}` | flag off (writes); a preview contact outside `visible()` |
| 409 | `{"detail": "stale_version"}` | a draft save or publish over a newer draft |
| 413 / 415 | `{"detail": "file_too_large"}` / `{"detail": "type_not_allowed"}` | a logo P-08's re-encoder refuses |
| 501 | `{"detail": "not_implemented"}` | until R-01-T26 |

## 7. Audit and outbox events
| Event | Written when | Payload |
|---|---|---|
| `portal_settings.draft_saved` | draft save | draft version |
| `portal_settings.published` | publish (Grace as actor) | version, content SHA-256 |
| `portal.preview_viewed` | preview | contact id or `sample`, device |

Outbox: `portal_settings.published {version}`.

## 8. Example payloads
ADM-10 b (Brightwater Hale, Grace Holloway, Mon Sep 14, 2026): the draft changes the cadence from 7 to 5 days; `next_reminder` reads last Mon Sep 14 9:00 AM, next Mon Sep 21 with `shifted_from` Sat Sep 19. ADM-10 g previews Tess Moreno (Copperleaf) on the phone: POR-02 d's projection, read-only.

## 9. Consumer contract tests
`backend/tests/contracts/c16_notifications/test_c16_v1_1_stub.py` and `test_c16_v1_1_consumers.py` (settings draft and publish shapes, the read-only preview). ADM-10's TypeScript fixtures arrive with R-01-T22.

## 10. Versioning
Additive to C16 v1.

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1.1 | (planned with R-01-T26) | | stub R-01-T16 |

## 11. Open points
Decided in DEC-378. POR-20's Reminder schedule edits save into this draft and publish from ADM-10 (`docs/screens/POR-20.md`, Open gaps).
