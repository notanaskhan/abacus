---
id: SPEC-345
title: "C16 v1.1: firm email templates, sending domains, the follow-up policy and portal settings (R-01, POR-20 and ADM-10) - the contract stub and its consumer suite"
status: draft
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-005, ADR-031, ADR-139, ADR-155, ADR-163]
related_specs: [SPEC-323]
created: 2026-10-26
updated: 2026-10-26
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - Scope: the C16 v1.1 contract (R-01 §8.2) as R-01-T16 stubs it and R-01-T17 tests it on behalf of its consumers. The behaviour behind it (drafts and publish R-01-T19, preview, lint, test send and import T23, the follow-up policy T24, portal settings T26, sending domains T27) is R-01 §3.7 to §3.9's stories; their ACs join this spec as those tasks start. C16 v1 (`docs/contracts/notifications.md`) is frozen and unchanged.

## 1. Summary
A firm edits, previews, tests and publishes its own client email templates (POR-20), sets its portal brand, client experience and reminder policy and previews the portal as a client would see it (ADM-10), and sends from its own verified domain. Module code sends a firm template only through `communications.api.send_templated`, which refuses rather than sends. This spec fixes the shapes, the slot and the refusals so the screens and the keys' consumers build against one contract.

## 2. Problem and context
R-01 §8.2 names C16 v1.1 (additive) with two documents, `docs/contracts/email-templates.md` and `docs/contracts/portal-settings.md`, consumed by P-06 (`request_sent`, `request_returned`, `reminder`), P-08 (platform-locked sign-in code on the same renderer), N-02 (`signature_request`), A-02 (`reconnect_request`), A-08 (`confirmation_request`), R-02, A-07 and T-02 (`deliverable_ready`), Q-04 (the onboarding import).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Firm admin (Grace Holloway) | Reads, edits, test-sends and publishes templates; manages portal settings and the sender domain; previews |
| Practice leader | Reads templates and settings |
| Security admin | Reads and manages the sender domain |
| Agent, system | Hold none of the actions; the system may send a published Reminder only behind `follow_ups.scheduled_send` (DEC-74) |
| Client principals | None of these routes |

## 4. Goals and non-goals
**Goals:** the routes, models, matrix rows, flags and slot of C16 v1.1 as stubs; consumer tests that pin the variable whitelist's safety.
**Non-goals:** template text (content, loaded by import or the editor), the renderer and lint (T23), the SES sender (T27), custom portal domains (later, DEC-59).

## 5. User stories and acceptance criteria
### Story 1: The stub (R-01-T16)
- **AC-1** Given the API, then the 19 routes of `email-templates.md` §2 and `portal-settings.md` §2 exist, each declaring one matrix action; template test send and publish, sending-domain create and settings publish take a required `Idempotency-Key`.
- **AC-2** Given the models, then every field is classified (ADR-031); C16 v1's models are unchanged (the frozen snapshot passes) and the firm import is a new `FirmEmailTemplateImportIn`.
- **AC-3** Given the matrix, then `email_template.{read,edit,test_send,publish,import}`, `sending_domain.{read,manage}`, `portal_settings.{read,manage}` and `portal.preview` exist (DEC-139 spells the plan's `portal.settings.*` with one dot); publish, import and both manage actions need `mfa_recent`; the agent and system are denied every one.
- **AC-4** Given `portal.settings_editor` off, then template and settings writes answer 404, and `communications.firm_sender_domain` off, sending-domain writes 404; reads and the import are not flag-gated; every route answers 501 until its task; `follow_ups.scheduled_send` decides whether a `send_on_schedule` policy may send. All three flags default off.
- **AC-5** Given `register_email_template`, then a key registers once, with whitelisted variables only, at most one call-to-action target per audience, screens by id, and staff templates are never firm-editable; `send_templated` takes the caller's `AuthContext` (or the scheduled-reminder `SystemSendContext`) and a `SendScope` naming the engagement, authorises `message.send` inside, refuses to run until R-01-T19, and its refusal reasons are `template_missing`, `template_lint_failed`, `out_of_scope`, `firm_not_client_facing`, `suppressed` (DEC-379).

### Story 2: The consumer suite (R-01-T17)
- **AC-6** Given each consumer's keys (P-06, N-02, A-02, A-08, R-02, R-01), then the variables they need are whitelisted, register through the slot, and the lint finding, settings draft and publish, and read-only preview shapes carry what their screens need.
- **AC-7** Given the whitelist, then no variable's kind can be an amount, an account number or a TIN, none is Restricted, and the variable kind type itself has no such member: the suite fails if one is ever added. Given client-written values (a document title "W-2 912-34-5678 $84,210.pdf"), then `lint_values` finds the TIN shape and the amount and the send refuses `template_lint_failed`, naming the code and the variable, never the value (DEC-379).

### Story 3: Previews never widen access (security review, DEC-379)
- **AC-8** Given a preview or test send for a real contact, then the contact must be visible to the viewer, every projected item is one the viewer could read themselves (`engagement.read` and the item's read action under `visible()`), dropped items leave no count, and with nothing readable the sample client renders; a firm admin walled off Copperleaf previews Tess Moreno as the sample client. `email_template.test_send` needs fresh MFA and an onshore member.

## 6. Behaviour and flows
As R-01 §3.7 to §3.9. The publish of a template or of portal settings writes one insert-only version in one unit of work; a draft carries `expected_version` and a stale save answers 409 `stale_version`.

## 7. Domain and data changes
None in the stub. R-01 §4.2's migrations (templates v2, follow-up policies, portal settings, sending domains) land with T19, T24, T26, T27.

## 8. Interfaces
`docs/contracts/email-templates.md` and `docs/contracts/portal-settings.md`. Module interface: `communications.api.register_email_template`, `registered_templates`, `send_templated`, `RecipientRef`, `SendActor`, `SendOutcome`, `SendRefusal`, `TEMPLATE_VARIABLES`, `FollowUpPolicyFields`, `NextSendOut`, `scheduled_send_enabled`.

## 9. Authorisation and tenancy
Firm-level actions through `authorise`; the preview's target contact is checked under `visible()` by the service (404 outside it, DEC-20); test send goes only to the acting admin.

## 10. AI behaviour
N/A: no model call; model text never enters a template (ADR P-25 off).

## 11. Integrations
SES (identities with Easy DKIM, custom MAIL FROM) behind the existing `SesIdentityPort` (T27).

## 12. Edge cases and failure modes
A key with no published version: `send_templated` records the message `blocked` with `template_missing`. A real firm before its M10 flip: client, third-party and respondent recipients are `blocked` with `firm_not_client_facing`; staff recipients are unaffected.

## 13. Security and privacy
Template text is Confidential (firm wording, sealed at rest by T19); variables are never Restricted and never an amount, an account number or a TIN; the lint refuses those shapes in typed text too; no address is stored in the suppression list, only its hash.

## 14. Audit trail and evidence integrity
`email_template.draft_saved`, `.draft_discarded`, `.test_sent`, `.published`, `.imported`; `portal_settings.draft_saved`, `.published`; `portal.preview_viewed`; `sending_domain.created`, `.verified`, `.failed`, `.revoked`; `message.blocked` with its reason.

## 15. Observability
Identifiers and codes only.

## 16. Performance and scale
Lists are short (templates ≤ 100, sending domains ≤ 10).

## 17. UX
POR-20 a-l and ADM-10 a-g (`docs/screens/POR-20.md`, `docs/screens/ADM-10.md`).

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-5 | contract | `backend/tests/contracts/c16_notifications/test_c16_v1_1_stub.py` |
| AC-6, AC-7, AC-8 | contract | `backend/tests/contracts/c16_notifications/test_c16_v1_1_consumers.py` |

## 19. Rollout
Flags `portal.settings_editor`, `communications.firm_sender_domain`, `follow_ups.scheduled_send`, all off. Rollback: revert; no data.

## 20. Open questions
- [x] Reads under the editor flag or not: not gated ("off → read-only published values", R-01 §0); DEC-378.

## 21. Future / explicitly deferred
The six keys' registrations and their content (T19, T22); the `sending_domain` and template-pill status words (DF-31, before T28).
