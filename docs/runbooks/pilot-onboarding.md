---
title: Pilot onboarding kit v1 (provision a firm and load it through its own screens)
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-05-28
---
# Pilot onboarding kit v1

| Field | Value |
|---|---|
| Owner | AY (partner-facing owner, `docs/ops/pilot/README.md`); N runs the operator commands |
| What it is | How a pilot firm goes from "no tenant" to "ready for `LEVEL=shadow`": provisioning, SSO and MFA, roles and walls, clients, PBC templates, email templates and branding, sender domain, retention, AI opt-in and stages, the support switch and status updates |
| Linked from | Q-04-T015 (this kit), Q-04-T016 and T018 (staging rehearsals, timed), Q-04 §3.5 AC-5.1 to AC-5.7; no alarm |
| Rehearse by | Fri May 28, 2027 (M8, PH2 exit "onboarding kit ready"): twice on staging with timings |
| Last rehearsed | never |
| Kill switches that apply | none: every step is the firm's own act or an audited operator command |

This is a procedure, not an incident runbook, so it carries no `RB-<nn>` number. It holds no
secrets, account ids, hosts or firm names: firms are pilot codes (PF-A1 …), names live only in the
founders' vault, and the dossier is `docs/ops/go-live/<pilot-code>.md` (Q-04 AC-6.5).

## Rules for every step

1. **Content goes in through the firm's screens, never through a commit.** Clients, PBC templates,
   email templates, branding, retention choices and walls are the firm's database rows, loaded by
   the firm's own people in their own screens (working agreement "content belongs in the
   database"; Q-04 AC-5.2). No step here edits a migration, a constant, a seed file or SQL. A PR
   that adds firm content anywhere outside `scenarios/brightwater_hale` is sent back (RK-63).
2. **The seed loader never touches a pilot firm.** `abacus_tools.synthetic` and `make seed-demo`
   refuse production and any firm that is not synthetic; they are for Brightwater Hale and the
   rehearsal tenant only.
3. **Accrued people never hold the firm's files.** The CCH Axcess export, the PBC workbook and the
   logo go from the firm admin's machine straight into the product (CLI-06, KNW-01, ADM-10). If a
   firm emails a file to the shared inbox, delete it unopened and ask them to upload it (Q-04
   AC-5.1).
4. **Every firm-side write is a person's act with a fresh second factor** where the contract says
   so, and is audited under that person (INV-5). Operator commands run as an ECS one-off
   `abacus-ops` task, never from a laptop against a hosted database, and audit as
   `operator:<handle>`.
5. **Evidence is a reference, never a copy.** Record the audit event id, the command's output
   status line, or the screen state seen, in the dossier. No screenshot of client data, no names, no
   amounts.

Each step below names **who** does it (operator: N or AY; firm: the firm admin, security admin or
quality partner), **where** (a screen state from the handoff, or a CLI), and the **evidence** that
it happened. Time every step during rehearsals in the table at the end.

## 0. Before day one

| Step | Who | Where | Evidence |
|---|---|---|---|
| 0.1 Pilot code assigned, name in the vault, dossier file created from the template | AY | `python -m abacus_tools.go_live_dossier new <pilot-code>` → `docs/ops/go-live/<pilot-code>.md` (PR, no firm name) | The dossier PR link |
| 0.2 Kickoff call booked: firm admin, security admin, quality partner, AY | AY | Shared inbox thread labelled `question`, pilot code | The ticket id |
| 0.3 The firm's plan and modules agreed (attest, tax, CAS, EBP) and its people list ready in its own format (RB-37 §0) | AY with the firm admin | Kickoff call | Plan code in the dossier |
| 0.4 The environment's notification templates imported before any switch that sends (`notification.mention`, `portal.sign_in_code`, the follow-up keys) | N | `POST /v1/platform/email-templates/import` (staff issuer, MFA; `docs/contracts/notifications.md`) | Import response ids in the dossier |

## 1. Provision the tenant

Until G-04 ships PLT-01 (S51) this is the CLI; afterwards PLT-01 **c** (Provision tenant… ·
Review) → **g** (Tenant created · invites sent to 2 first admins).

| Step | Who | Where | Evidence |
|---|---|---|---|
| 1.1 Provision with the agreed plan and the two first admins | N | `python -m abacus_tools.tenants provision --name <vault ref> --slug <pilot-code slug> --plan <plan> --admins <a>,<b> --idempotency-key provision-<pilot-code>-1 --operator <handle>` (an `abacus-ops` task; region is always `us`, ADR-156) | The tenant id; `tenant.provisioned` audit event |
| 1.2 Confirm the workflow finished (keys, plan, entitlements, invitations) | N | `python -m abacus_tools.tenants status --tenant <tenant_id>` | Status line `completed` in the dossier |
| 1.3 Module entitlements beyond the plan, if the agreement says so | N | `make entitlement FIRM=<tenant_id> MODULE=<module> ENABLED=true SEATS=<n> OPERATOR=<handle> REASON="pilot agreement"` | `tenant.entitlements_changed` audit event |
| 1.4 The retention defaults set is the published one | N | `python -m abacus_tools.tenants retention-defaults --operator <handle>` (only if the platform set changed since the last firm) | The set version in the dossier |

A repeated `provision` with the same idempotency key returns the same tenant and starts no second
workflow: a retry is safe.

## 2. First sign-in, SSO and MFA

| Step | Who | Where | Evidence |
|---|---|---|---|
| 2.1 Both first admins accept their invitations and enrol a second factor | Firm admins | The invitation email → sign-in | ADM-02 **a** lists both as active |
| 2.2 Connect the firm's identity provider and require SSO | Security admin | ADM-06 **i** (Require SSO · Per user); `PUT /v1/firm/security/sign-in` (fresh MFA) | `GET /v1/firm/security` shows SSO required |
| 2.3 Designate the break-glass account exempt from SSO (one, MFA on) | Security admin | ADM-06 **a**; `PUT /v1/firm/security/sso-exempt-account` (fresh MFA) | The exempt account set in the overview |
| 2.4 SCIM, if the firm uses it, syncs without error | Security admin | ADM-06 **j** must not show (SCIM error) | Posture read clean |
| 2.5 MFA at 100% of staff before any shadow run | Security admin | ADM-06 **e** (MFA gap) must be empty; `GET /v1/firm/security/posture` | Posture: MFA 100% (go-live check item) |
| 2.6 Portal sign-in rules for owners and signers (needed before `LEVEL=client_facing`) | Security admin | ADM-06 **a**, fieldset B; `PUT /v1/firm/security/portal-sign-in` (fresh MFA) | The overview's portal fieldset |

## 3. People, roles, offices and walls

Follow `RB-37-onboard-firm-people-and-walls.md` end to end; it is the procedure for this step.

| Step | Who | Where | Evidence |
|---|---|---|---|
| 3.1 Offices and teams | Firm admin | ADM-03 **a** | `GET /v1/firm/offices`, `GET /v1/firm/teams` |
| 3.2 Invite people with level and office; seats respected | Firm admin | ADM-02 **a**, invite drawer **c** (seats full shows when the plan is used up), pending **f** | `GET /v1/firm/staff` tallies match the firm's list |
| 3.3 Firm roles and security roles mapped | Firm admin, security admin | ADM-02 **b** (Role templates), **d** (user drawer) | `identity.roles_mapped` in `make go-live-check` (admins present, every staff member on a role template; G-01-T19) |
| 3.4 Service-line separation | Firm admin or partner | ADM-03 **h** (Service line · Tax narrowed) | `service_line_policy.updated` audit event |
| 3.5 Offshore group and its preconditions, only if the firm has offshore staff | Firm admin | ADM-03 **d**, **f** | RB-37 §4 checklist in the dossier; `identity.offshore_consent_gated` in `make go-live-check` (G-01-T19) |
| 3.6 Every declared conflict walled and approved by its named partner; no unresolved conflict | Firm admin, the named partner | ADM-03 **b** (New ethical wall) → partner approves; **c** (Wall conflict) must not remain; **g** (Wall log) | Wall ids in the dossier; `j02-client-onboarding` staging run asserts INV-3 for a walled user (AC-5.5) |

`make go-live-check FIRM=<id> LEVEL=shadow` reads the three M9 rows (G-01-T19, DEC-903): `identity.roles_mapped`, `identity.walls` (pass with an active wall; manual when none, confirmed in the dossier) and `identity.offshore_consent_gated`.

## 4. Clients and contacts (bulk import)

| Step | Who | Where | Evidence |
|---|---|---|---|
| 4.1 The firm admin exports from CCH Axcess (or the CSV template) on their own machine | Firm admin | Their practice system | Nothing is sent to Accrued |
| 4.2 Upload the file | Firm admin | CLI-06 bulk import; `POST /v1/client-imports?source=&filename=` (`client_import.run`) | Import id |
| 4.3 Fix validation findings, if any | Firm admin | CLI-06 **i** (Validation) | Re-upload id |
| 4.4 Review duplicates: every "to review" row decided (match, merge or new) | Firm admin | CLI-06 **g** ("204 matched + 8 review" for the rehearsal file); `PUT …/rows/{row_id}/decision` | `GET /v1/client-imports/{id}` shows `to_review: 0` |
| 4.5 Run the import | Firm admin | CLI-06 **g** → Run; `POST …/{import_id}/run` with `Idempotency-Key` (202) | Clients exist attributed to the admin (INV-5); `client_import.row_decided` audit events |
| 4.6 The file is gone after 30 days | Nobody (the import's retention) | `docs/contracts/intake-import.md` | Dossier note with the delete-after date |

## 5. PBC templates and the methodology

| Step | Who | Where | Evidence |
|---|---|---|---|
| 5.1 Import the firm's PBC template workbook as an engagement template version | Quality partner | KNW-01 **h** (Engagement templates); `POST /v1/methodology/templates/{name}/versions?engagement_type=&family=` | Version id |
| 5.2 Approve it | Quality partner (not the importer where the policy says so) | KNW-01 **c** (Review queue) → approve | `methodology_version.approved` audit event (human-only) |
| 5.3 It is published and visible to staff | Quality partner; one staff member checks | KNW-01 **a** (Published), **e** (Staff viewer) | The card in KNW-01 a |

## 6. Email templates

| Step | Who | Where | Evidence |
|---|---|---|---|
| 6.1 Start from the defaults, or import the firm's wording | Firm admin | POR-20 **a** (Reminder · draft v4); `POST /v1/firm/email-templates/import` (fresh MFA) | Draft per key |
| 6.2 Edit each key the firm will use: Reminder, Invitation, Signature request, Deliverable ready, Confirmation request, Reconnect request | Firm admin | POR-20 **b** (Editing), **e**–**i** for the other keys; lint findings resolved inline | Drafts saved |
| 6.3 Preview desktop and phone | Firm admin | POR-20 **c** (390), **d** (Phone) | — |
| 6.4 Test send goes only to the admin's own address | Firm admin | POR-20 **j** (Send test…) → **k** (Test sent); `POST …/{key}/test-send` (fresh MFA, onshore) | The test arrives in the admin's inbox only (AC-5.3) |
| 6.5 Publish every key the first client invitation uses before M10 | Firm admin | POR-20 **l** (Published); `POST …/{key}/publish` (fresh MFA) | Published versions (go-live check `LEVEL=client_facing`) |

## 7. Branding and the sender domain

| Step | Who | Where | Evidence |
|---|---|---|---|
| 7.1 Logo, colours, portal wording; preview as a client | Firm admin | ADM-10 **a** → **b** (Dirty) → **c** (Phone preview) → **g** (Preview as a client contact) | Draft saved |
| 7.2 Add the firm's sending domain and give the DNS records to the firm's IT | Firm admin or security admin | ADM-10 **d** (Pending DNS); `POST /v1/firm/sending-domains` (fresh MFA). Until R-01-T27 lands these routes answer 501: record the domain in the dossier and repeat this step when they are live | Domain id, or "pending R-01-T27" |
| 7.3 While DNS is unverified the portal uses the neutral fallback host, never one containing "accrued" | AY checks | ADM-10 **d** | Host checked (AC-5.4) |
| 7.4 DNS verified; publish | Firm admin | `POST …/sending-domains/{id}/check` → ADM-10 **f** (Published); `POST /v1/firm/portal-settings/publish` (fresh MFA) | Sender domain verified (go-live check `LEVEL=client_facing`) |

## 8. Retention policies

| Step | Who | Where | Evidence |
|---|---|---|---|
| 8.1 Review the effective policy per record type in scope; change only above the platform floor | Firm admin or security admin | ADM-06 **h** (WISP, residency & retention); `GET /v1/retention/policies`, `PUT /v1/retention/policies` (fresh MFA) | `retention_policy.updated` audit events, or "defaults kept" (go-live check item) |

## 9. AI opt-in and agent stages

| Step | Who | Where | Evidence |
|---|---|---|---|
| 9.1 The firm reads the AI disclosure and opts in to agents on its client data | Firm admin (or the security admin for the client-data section) | ADM-04 **h** (Auto mode & client data); `GET`/`PUT /v1/firm/ai-client-data` | `firm.ai_client_data_opted_in` audit event against the current disclosure (AC-5.6) |
| 9.2 Each in-scope agent at stage `shadow` for this firm | N (founder, owner credentials) | `make agent-stage FIRM=<tenant_id> AGENT=<agent> STAGE=shadow NOTE="PW1 shadow"`; report with no `STAGE` | The stage report per agent in the dossier |
| 9.3 The firm's AI policy version, once ADM-04's services are live (G-02; stub today) | Quality partner | ADM-04 **a** → **d** (Save as v4…) → **g** (v4 published) | Version number, or "pending G-02" |

## 10. The support switch

| Step | Who | Where | Evidence |
|---|---|---|---|
| 10.1 The firm decides whether Accrued may ask for support sessions; each session is still the firm's approval, one work item or return, at most 2 hours, US-located staff only where tax data is involved (DEC-72) | Security admin | ADM-06 **a**, support switch; `GET`/`PUT /v1/firm/support-access` (fresh MFA) | The switch state (go-live check item) |

## 11. Status updates

| Step | Who | Where | Evidence |
|---|---|---|---|
| 11.1 The firm admin and security admin subscribe to the status page themselves (firm-facing only; the portal never links to it, ADR-154) | Firm admin, security admin | The SHL-05 support drawer's "System status" link → Subscribe | AY sees two subscribers for the pilot code in Better Stack (count only, in the vault reference, never in git) |
| 11.2 AY confirms the firm knows the shared inbox, the labels and office hours | AY | `docs/ops/pilot/README.md`, kickoff follow-up | The ticket id |

## 12. Ready for `LEVEL=shadow`

| Step | Who | Where | Evidence |
|---|---|---|---|
| 12.1 Run the go-live check | N | `make go-live-check FIRM=<tenant_id> LEVEL=shadow` (Q-04 group F; until it lands, walk Q-04 AC-6.1's list by hand and mark each item from the evidence above) | Pass per item, "manual" items linked to their dossier section |
| 12.2 Both founders sign the dossier | AY, N | The dossier PR | Two approvals (AC-6.5) |
| 12.3 Between Jan 15 and Apr 15 nothing client-facing goes live; there is no override | AY | The check fails for `LEVEL=client_facing` in that period (AC-5.7) | — |

## Never

- Never load a firm's clients, templates, branding or policies through a commit, a migration, a
  constant, the seed loader or SQL.
- Never take a firm's file by email, chat or shared drive; never open one that arrives.
- Never sign in as a firm user, and never act in a firm's screens for them; screen-sharing on the
  kickoff call is the firm's person clicking.
- Never put a firm name, person, client, amount or file in a ticket, a dossier, a commit or this
  runbook.

## Timings (fill in at each rehearsal)

The rehearsals' input files (a 200-client CCH-headed list and a Workbook v2 PBC template) come
from `python -m abacus_tools.synthetic.onboarding_files --out <scratch dir>`; part AY's step-by-step
record is `docs/ops/rehearsals/onboarding-content-part-ay.md`.

| Section | T016 rehearsal (N part) | T018 rehearsal | First pilot firm |
|---|---|---|---|
| 0 Before day one | | | |
| 1 Provision | | | |
| 2 SSO and MFA | | | |
| 3 People and walls | | | |
| 4 Bulk import | | | |
| 5 PBC templates | | | |
| 6 Email templates | | | |
| 7 Branding and sender domain | | | |
| 8 Retention | | | |
| 9 AI opt-in and stages | | | |
| 10 Support switch | | | |
| 11 Status updates | | | |
| 12 Go-live check | | | |
