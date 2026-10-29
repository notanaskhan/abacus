# ADM-06 · Security center & data residency

| Field | Value |
|---|---|
| Route and params | `/settings/security` behind `security_center.v1` (G-02 §5.1). Anchors `#sign-in`, `#portal`, `#incidents`, `#wisp`, `#residency`, `#retention`; `?incident=INC-2026-005` opens the drawer; `?sessions=1` opens the sessions drawer; `?export=history` opens the O1 tray. Legacy `/admin/support` → `/settings/security#support` |
| Template and host frame | T12 two-column (fieldsets 760 + cards 330), section "Security"; Fieldset, ValueRow, Toggle, Lock, a table inside a fieldset, cards, StatusDisc, O1 tray 462, O2 drawer 480, Dialog 460, Toast |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ADM-06 Security center and data residency/` (README.md, spec.md, revision.md: R2 wave 8 enterprise identity; revision wins for what it lists) |
| Epic and tasks | G-02 · contract stub T11 · AC suite T12 · security policies T14 · screen T16 · incidents T18 · export schedule T19 · safeguards T20 · parity and journeys T21 · seed T07 · this contract T03 |
| Manifest status | planned (`routes/manifest/adm.ts`): built by G-02-T16 behind `security_center.v1` |

Code (G-02-T16): `apps/web/src/screens/ADM-06/{index.tsx, scenarios.ts, copy.ts, ADM-06.test.tsx}`, `apps/web/src/domain/governance/`.

## States

10 artboards: a–f from the original handoff, g–h new in the epic's build list, and revision R2's g and h mapped here as **i** (Per user) and **j** (SCIM error).

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Owner · status |
|---|---|---|---|---|---|
| a | felix-andersen (IT / Security, Qualified Individual) | Mon Sep 14, 2026, 9:24 AM CT | E0 | SSO enforced Jan 12, 2026 by Felix; MFA 46 of 46; INC-2026-003/004/005 (005 day 4 of 30); exports Jul 1 / Aug 1 / Sep 1; support session Aug 17 closed; WISP v4; 18 of 20 controls | G-02-T16 · fixture + staging |
| b | felix-andersen | 9:24 AM | E0 | "Export now…" → Dialog 460 "Export all firm data?" (Margaret Okonkwo must approve; link expires after 7 days) | G-02-T16, T19 · fixture + staging |
| c | felix-andersen | 9:24 AM | E0 | `?export=history`: O1 tray, Actions (Export now · Change schedule), History Sep 1 386 GB · Aug 1 371 GB · Jul 1 359 GB | G-02-T16, T19 · fixture + staging |
| d | felix-andersen | 9:24 AM | E0 | `?incident=INC-2026-005`: O2 drawer, timeline, clock bar 4/30, "Close as not reportable…" (Partner + QI) · "Start notification…" | G-02-T16, T18 · fixture + staging |
| e | felix-andersen | Sun Jan 11, 2026 | dated snapshot | before enforcement: "41 of 46 enrolled" red ink + amber banner "5 users without MFA. Enforcing SSO will require MFA at next sign-in." | G-02-T16 · fixture (dated snapshot) |
| f | margaret-okonkwo (Partner, not `security_admin`) | 9:24 AM | E0 | read-only: banner and Lock 12 on bands; Export now hidden; Approve export visible | G-02-T16 · fixture + staging |
| g | felix-andersen | 9:24 AM | E0 | after b: card pill "Waiting for approval · Margaret Okonkwo"; ADM-07 event "Data export requested by Felix Andersen" | G-02-T16, T19 · fixture + staging |
| h | felix-andersen | 9:24 AM | E0 | scrolled to WISP, residency and retention (retention read-only, FIL-02 planned link) | G-02-T16, T20 · fixture + staging |
| i | felix-andersen | 9:24 AM | E0 | R2: Require SSO "Per user": 46-row toggle table, break-glass account exempt with Lock 12 | G-02-T16 · **fixture only** (live with G-03-T29) |
| j | felix-andersen | 9:24 AM | E0 | R2: SCIM error, Last sync red ink "1 user not provisioned · seat limit 46 of 46" + "Open seats (ADM-02) →" | G-02-T16 · **fixture only** (live with G-03-T29) |

**New v1 frames (G-02-T03 revision; built by T16):** the Sessions row and drawer with "Sign out of Brightwater Hale" (`?sessions=1`); the unlock action on a locked member; the IdP-MFA attestation row; support-session states "Awaiting firm approval", "Granted until …", "Revoked"; retention rows read-only with the FIL-02 planned link. The revision R2 fieldset A rows (Require SSO segmented, Exceptions, IdP-initiated SSO, SCIM provisioning sub-header, Posture "SCIM provisioning on") are fixture-only with i and j until **G-03-T29** (S70).

Non-artboard states: loading, error, not-allowed (client, agent, system: never rendered), flag off (route absent; `/admin/support` unchanged).

## API

| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons |
|---|---|---|---|---|
| read | `GET /v1/firm/security` | sign-in, portal, MFA summary, residency, retention (read-only), safeguards, export card, support, posture | `security.read` | `security_admin` edits; partners read (f) |
| write | `PUT /v1/firm/security/sign-in` | `require_sso`, session limits, IdP-MFA attestation (If-Match); 409 `sso_not_verified`; 422 `policy_loosening_refused` | `security.manage` (fresh) | `security_admin` |
| write | `PUT /v1/firm/security/portal-sign-in` | portal session length (shorten only); floors locked | `security.manage` (fresh) | `security_admin` |
| write | `PUT /v1/firm/security/sso-exempt-account` | the one SSO-exempt account | `security.manage` (fresh) | `security_admin` |
| read / write | `GET /v1/firm/security/sessions`; `POST …/sessions/{id}/sign-out` | active sessions of current members; revoke this tenant on a session | `security.read` / `session.end` (fresh) | `security_admin` |
| write | `POST /v1/firm/staff/{user_id}/unlock` | clear a sign-in lock where WorkOS allows | `staff.unlock` (fresh) | `security_admin` |
| read / write | `GET/PUT /v1/firm/support-access`; `/support-sessions` routes | "Allow support session requests"; approve, revoke, acknowledge | `support_session.read` / `support_session.manage` | `security_admin`, firm admin |
| read / write | `GET /v1/firm/security/incidents`, `…/{id}`; `POST …/{id}/timeline`; `POST …/{id}/decisions` | register, drawer, timeline, two-person decisions | `incident.read` / `incident.manage` / `incident.decide` (fresh) | QI and a partner decide |
| read / write | `GET /v1/firm/data-exports`; `GET/PUT …/schedule`; `POST …/schedule/approve`; Q-02's `POST /v1/firm/data-exports`, `…/{id}/approve` | card, history (last 12), schedule with dual approval | `firm_export.read` / `.schedule` / `.approve` (fresh) | requester `security_admin`; approver a partner |
| read / write | `GET/PUT /v1/firm/safeguards`, `PUT …/controls/{key}`, `POST …/wisp-pack` | safeguards record, control status, WISP pack (202) | `security.read` / `security.manage` | `security_admin` |
| read | `GET /v1/firm/security/posture` | five posture facts | `security.read` | — |

Contract: `docs/contracts/` security-center family (G-02-T11) and `compliance-kernel.md` (Q-02).

## Status

Incident status (Investigating, Closed), FTC clock pill (amber "Day 4 of 30 · notify by Oct 10 if ≥ 500"), muted "Not a notification event", export pills (green-tint "Scheduled", spinner "Waiting for approval · Margaret Okonkwo"), support session (Closed; new: Awaiting firm approval, Granted until …, Revoked).

## Copy

Verbatim from the handoff spec and revision via `copy.ts`, with the T03 deviations: fieldset B's MFA row is a locked floor with DF-17 copy ("…for owners, signers, approvers and anyone who can see tax return information"); lockout reads DEC-35 ("3 codes · 15 minutes"). Helper (fieldset C): "FTC Safeguards Rule, 16 CFR 314.4(j): notify the FTC as soon as possible and no later than 30 days after discovering a notification event involving unencrypted customer information of 500 or more consumers. State breach laws may also apply."

## Links

| From | To (manifest builder) | Planned or live |
|---|---|---|
| Settings navigation rail: Settings home · Offices & teams · AI policy · Consents · Developer · Integrations · Portal · Quality · Monitoring | ADM-01 · ADM-03 · ADM-04 · ADM-05 · ADM-09 · ADM-08 · ADM-10 · ADM-11 · ADM-12 | live where built, as ADM-01's section rows; "not built yet" in dev and fixture builds, hidden in production (ED-113) |
| "Legal holds ›", retention helper | FIL-02 (Q-05) | planned |
| WISP "Open ›" | FIL-01 (N-01) | planned |
| support access | PLT-01 (G-04) | planned |
| "Open seats (ADM-02) →" (j) | ADM-02 | live |
| every change | ADM-07 `?target=…` | live with G-02-T13 |

## Acceptance

- ADM-06 acceptance: the FTC clock is correct: discovered Sep 10 → day 4 on Sep 14 → deadline Oct 10; threshold 500 consumers, unencrypted information.
- ADM-06 acceptance: MFA 46 of 46 matches ADM-02; SSO enforced since Jan 12, 2026.
- ADM-06 acceptance: retention defaults match domain D.6 (7 years; audit documentation WORM after assembly; consents life of relationship + 7) and are read-only.
- ADM-06 acceptance: the data export card shows schedule, contents, encryption, last and next run and two-person approval; the requester never approves.
- ADM-06 acceptance: residency is US-only and locked; the support card agrees with PLT-01 (Aug 17 session, closed).
- ADM-06 acceptance (R2): Require SSO offers All users · Per user with one break-glass exception; SCIM shows 46 of 46 seats and the five ADM-03 groups; the error state points to ADM-02 without naming a new person (fixture only).

## Figures

- MFA 46 of 46 (e: 41 of 46 on Jan 11, 2026); training 46 of 46; PTIN 21 of 21; Pub 4557 controls 18 of 20.
- Exports Sep 1 386 GB · Aug 1 371 GB · Jul 1 359 GB; next Oct 1, 2026.
- INC-2026-005 discovered Sep 10: day 4 of 30 on Sep 14, notify by Oct 10 if ≥ 500; 1,812 failed sign-ins from 203.0.113.0/24 blocked.

## AVOID

Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, red alarm banners for routine items, security "scores" or gauges, real IP addresses outside 203.0.113.0/24; (R2) turning SSO off for a whole office, showing passwords or secrets, changing incidents, WISP, residency or retention.

## Deviations

| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-1 | Portal MFA row is a locked floor with DF-17 copy, not "Require MFA for owners and signers" toggle | DF-17: the floor covers anyone who can see tax return information | DEC-411 |
| DV-2 | Lockout reads "3 codes · 15 minutes" (locked), not "5 attempts ⇕" | DEC-35 | DEC-35, DEC-411 |
| DV-3 | Sessions, unlock, IdP-MFA attestation and support-session states are new v1 frames | v1 behaviour the handoff did not draw | DEC-411 |
| DV-4 | Retention fieldset is read-only with a planned FIL-02 link | P-14 editing belongs to FIL-02 (Q-05) | G-02 §2.3; DEC-411 |
| DV-5 | R2 enterprise-identity rows and i, j fixture-only | live per-user SSO and SCIM are G-03-T29's | G-02 §2.3; DEC-411 |

## Parity

| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| e | C (locked) | 2.84 | locked 2026-10-29 (G-02-T26), measured on `parity-screens` |
| a, c, f, g, h | C report-only | 3.09 / 3.08 / 3.10 / 3.31 / 3.09 | G-02-T21 recorded these as locked on 2026-10-27 before any baseline existed; measured 2026-10-29 (G-02-T26) each is 0.08–0.31 points over 3 %: fieldset B copy (DV-1, DV-2) until the boards are revised (open gap) |
| b, d | C report-only | 12.38 / 6.26 | over 3 % (measured 2026-10-29); open gap |
| i, j | C report-only | 3.30 / 3.25 | fixture mode only |

## Open gaps

- The design-tool frames for the new v1 states and the design-fidelity sign-off are made on the Wave 3 canvas outside the repository.
- Revision R2's new-state letters g and h collide with the original build list; this contract calls them i and j.
