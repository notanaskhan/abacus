---
id: SPEC-349
title: "Firm governance v1 (G-02): the AI policy, the security center and the audit log (ADM-04, ADM-06, ADM-07)"
status: approved
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-005, ADR-007, ADR-020, ADR-024, ADR-026, ADR-027, ADR-031, ADR-061, ADR-078, ADR-089, ADR-139, ADR-141, ADR-146, ADR-147, ADR-157, ADR-159, ADR-161, ADR-164, ADR-165, ADR-167, ADR-179, ADR-186, ADR-187]
related_specs: [SPEC-012, SPEC-024, SPEC-036, SPEC-304, SPEC-341]
created: 2026-10-26
updated: 2026-10-26
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves. The AC numbers are the epic's (`docs/plan/epics/G-02.md` §3, AC-1 to AC-49), restated in §5 so tests cite this spec.
> - Solo edition (`docs/plan/AMENDMENT-solo.md`): "N", "AY", "both founders", approval files and Contract Monday minutes read as "the builder" and a decision-log row. ADR-078's separate test author is void: AC suites are written first, from this spec.
> - The gate check (G-02-T01, TASK-1289) is §22; the decisions it took are DEC-415.

## 1. Summary
Three firm-settings screens let Brightwater Hale's governance owners prove that every AI output was approved by a named human under a written, versioned policy, that staff sign in the way the FTC Safeguards Rule requires, and that every change left an immutable, attributable trace. **ADM-07 Audit log** is the firm-wide, immutable, filterable log with request context and read-time masked values. **ADM-06 Security** holds sign-in enforcement, the portal floor, sessions, the incident register, WISP and Pub 4557 evidence, residency, read-only retention, the dual-control firm export and the support-access switch. **ADM-04 AI policy** is the versioned "BH AI policy vN" (ADR-186) with three immediate controls outside versioning.

## 2. Problem and context
- Epic G-02 (`docs/plan/epics/G-02.md`) wrote AC-1 to AC-49 in §3; this spec gives them one home and binds them to the decisions taken at the gate check.
- The compliance kernel (Q-02, SPEC-341) supplies the attribution columns, hash chain, incident register, firm-export stub, retention floors, MFA enforcement and the TASK-076 opt-in. G-02 consumes them and never re-implements them.
- Today: `GET /v1/firm/audit-events` (SPEC-304, TASK-305) lists identifiers only to firm admins; `PUT /v1/firm/autonomy` (SPEC-024 AC-5, TASK-042) sets one autonomy level; `Autonomy.tsx` and `SupportAccess.tsx` are legacy cards. §21 says what supersedes each.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Felix Andersen, IT/Security, `security_admin` (the Qualified Individual) | Reads the audit log as metadata; exports it with fresh MFA; manages sign-in policy, sessions, unlock, incidents, the export schedule and support access |
| Margaret Okonkwo, Managing Partner, `quality_partner` (QM owner) | Reads values in scope; drafts and requests AI policy versions; second decider on incidents and exports |
| Daniel Reyes, partner (`level_in(partner)`) | Approves an AI policy version requested by someone else; approves exports |
| Grace Holloway, `firm_admin` | Reads the audit log as metadata; opts the firm in to AI on client data (SPEC-036); pauses agents; AI policy read-only |
| Hannah Leclerc, Manager | AI policy read-only ("Only partners can change the AI policy.") |
| The Accrued Agent | Appears only as "‹person› via Agent"; denied every G-02 write |
| The system | Scheduled runs (export, reminders, label index); attributed "System" |
| Client principals | No access: every `/v1/firm/*` and `/v1/audit-events*` route answers 404 |

## 4. Goals and non-goals
**Goals**
- ADM-04, ADM-06 and ADM-07 built to AC-1 to AC-49, with ADM-04 c, f, ADM-06 i, j and ADM-07 d fixture-only.
- J01 steps 2 and 8 and J14 step 7 walkable on staging by M8 (Fri May 28, 2027).

**Non-goals** (G-02 §2.3)
- Enabling the policy principal (ADR-187: dormant before GA).
- Auto mode enforcement in run planning (P-10).
- Live per-user SSO, IdP-initiated SSO and SCIM (G-03-T29).
- Editing retention defaults, legal holds or destruction (Q-05, FIL-02).
- ADM-04 fieldsets F and G and state k (K-04, K-05, I-03-T37).
- A dual-approval audit-log export: ADM-07's export is one person with fresh MFA (DEC-415 Q8).

## 5. User stories and acceptance criteria
The text below is the epic's §3, numbered as there. Where the gate check decided a point, §20 records it.

### 5.1 See who did what, firm-wide (ADM-07a, b, f)

*As Felix Andersen, the firm's Qualified Individual, I want one immutable log of every event with who, what, from where and through which run, so I can answer a reviewer or an insurer without asking engineering.*

- **AC-1** *Given* Felix at E0, *when* Felix opens `/settings/audit-log`, *then* the past-7-days feed lists events newest first, each row with its own date over its time (no day bands), an ok/no/pl marker from the activity catalogue, a 13.5/500 title composed by the SPA from the action code and facts, the object chip, the actor-type tag and the IP; the header reads "18,406 events · immutable" with Lock 12, and the note reads "Policy principal: 0 events — policy acceptance is off (AI policy v3)" (**ADM-07a**).
- **AC-2** *Given* the Actor filter "via Agent", *then* only events with `actor_kind='agent'` and an `on_behalf_of_user_id` are listed, each titled "‹person› via Agent" with the atom glyph, the chip turns amber-tint and the count reads "4 of 1,962" (**ADM-07b**, INV-5).
- **AC-3** *Given* any action code the catalogue marks as an approval, acceptance, sign-off, release, send, post or export, *then* no event with that code has `actor_kind='agent'` (generated test over the catalogue and the database CHECKs), and no row anywhere reads "Accrued Agent" as an actor of such an action (**INV-1**, INV-5, lint L5/L6).
- **AC-4** *Given* a viewer walled from Ashford Manufacturing, *then* no event whose `client_id` is Ashford is returned, the counts exclude them, and nothing says that rows are hidden (**INV-3**, DEC-43).
- **AC-5** *Given* Grace Holloway (`firm_admin`) or Felix (`security_admin`), *then* events are returned as metadata (actor, verb, object label, time, IP) and value sections answer `values_withheld` with reason `need_to_know`; *given* Margaret Okonkwo (`quality_partner`, `in_scope`), *then* values resolve (DEC-60, ADR-024).
- **AC-6** *Given* the search "pell street iii", *then* the empty state reads "No events match 'pell street iii'." / "Search covers actors, objects and details." (**ADM-07f**); *given* a seeded SSN anywhere in a target, *then* no search for any part of it returns a row.
- **AC-7** *Given* a click on an IP, *then* the feed filters to that IP; the Date and Office chips filter on `effective_at` and the event's office; "Load more" pages by keyset on `seq` and stays stable while new events arrive.
- **AC-8** *Given* the route table, *then* no route updates or deletes an audit event (route introspection), the database still refuses `UPDATE`/`DELETE` for the app role, and the drawer footer reads "Immutable. Corrections are new events."
- **AC-9** *Given* a human request through the BFF, *then* its event carries `ip`, `device_label`, `session_id`, `auth_method` and `mfa_at`; a support-session write carries the support engineer's request context with `auth_method='support'`; agent and system writes leave them null and the row shows "—".

### 5.2 Read one event in full (ADM-07c)

- **AC-10** *Given* Margaret opens the Copperleaf batch (fixture; on staging, a seeded event of a built type), *then* the O2 480 drawer shows Actor (name, level, office), Authority, Time to the second in the firm time zone, IP/device, Session ("SSO · MFA 9:01 AM"), Content hash (`sha256 …`), the before → after table, "Not included" facts, Source ("Proposed by Raj Malhotra via Agent · Close run 2 · started 9:06 AM") with "Open run trace ›" as a planned link to WB-09 until P-09 (**ADM-07c**).
- **AC-11** *Given* a Restricted field among the values, *then* it is shown only masked (`•••-••-2208`), and a generated test proves no Restricted value is stored in `audit_events`, `audit_event_labels` or an export (DEC-60, ADR-031).

### 5.3 Export the log (ADM-07e, g)

- **AC-12** *Given* Felix chooses Export… for Sep 8–14, 2026, *when* the session's MFA is older than the fresh window, *then* the T12 step-up slot asks for a second factor first; *then* the job builds `audit-log-2026-09-08-2026-09-14.csv`, `manifest.json` and `manifest.sig`, the toast reads "Export ready · SHA-256 manifest included" (**ADM-07e → g**), the link expires within 7 days, and creation and download each write an audit event naming Felix.
- **AC-13** *Given* the bundle, *then* `shasum -a 256` of the CSV equals the manifest's digest, the signature verifies with the environment's published export-signing public key, and the manifest carries the seq range and the P-43 hash-chain checkpoint covering it.
- **AC-14** *Given* "Include before/after values" on, *then* values appear only as the requester could see them on screen; *given* the agent principal or any client principal, *then* every export route answers 403 (INV-1, **INV-4**).

### 5.4 Firm sign-in (ADM-06a, e)

*As Felix, I want staff to sign in only through Entra ID with a second factor, within session limits we choose, with one emergency account, so the firm meets 16 CFR 314.4(c)(5).*

- **AC-15** *Given* no verified admin SSO sign-in exists, *when* Felix turns on "Require SSO", *then* the API answers 409 `sso_not_verified` (SPEC-024 §12); *given* one, *then* enforcement starts, Grace's email-code sign-in is refused with the SHL-06 SSO-enforced state, and ADM-07 logs "SSO enforced by Felix Andersen".
- **AC-16** *Given* E0, *then* MFA reads "Enforced · 46 of 46 enrolled" (green ink) and cannot be turned off (DEC-22); *given* the Jan 11, 2026 snapshot, *then* it reads "41 of 46 enrolled" in red ink with the amber banner "5 users without MFA. Enforcing SSO will require MFA at next sign-in." (**ADM-06e**). For SSO users whose IdP enforces MFA, the count uses the IdP's MFA claim only after Felix records the "IdP enforces MFA" attestation (P-01 hand-off, R-29).
- **AC-17** *Given* the platform maxima (12 h absolute, 30 min idle), *then* Felix may only shorten them (422 `policy_loosening_refused` otherwise); *given* a session idle for longer than the firm's limit, *then* the next refresh fails and the person signs in again.
- **AC-18** *Given* Felix designates the SSO-exempt emergency account with a fresh second factor, *then* exactly one may exist in v1, it must hold a hardware-key factor, "last tested" is recorded when it signs in, and both are logged.

### 5.5 Portal sign-in floor (ADM-06a, fieldset B)

- **AC-19** *Given* fieldset B, *then* "Passwordless email code" is on and locked; "Require MFA for owners, signers, approvers and anyone who can see tax return information" is on and locked (DEC-34, DF-17; P-08's floor predicates); "Lock after failed codes" reads "3 codes · 15 minutes" (DEC-35); portal session length may only be shortened from 8 h; any loosening answers 422 and is never offered (INV-4 isolation of portal identities is unchanged).

### 5.6 Sessions and unlock (new v1 rows)

- **AC-20** *Given* Felix opens Sessions, *then* the list shows active sessions of current Brightwater Hale members only (person, device, IP, started, last seen, MFA time); *when* Felix chooses "Sign out of Brightwater Hale" with a fresh second factor, *then* that session can no longer act in this tenant, an `access.changed` event closes its SSE streams and caches, other tenants of the same person are unaffected, and ADM-07 logs it. *Given* a locked staff account, *then* "Unlock" (security_admin or firm_admin, fresh MFA) clears the lock if WorkOS exposes it; otherwise the row reads "Unlocks automatically at 9:39 AM" (DEC-35) [verify WorkOS, §11.2].

### 5.7 Incident register (ADM-06a fieldset C, d)

- **AC-21** *Given* E0, *then* INC-2026-005 shows "0 confirmed" and the amber pill "Day 4 of 30 · notify by Oct 10 if ≥ 500" with state Investigating; INC-2026-004 and -003 show "Not a notification event" and Closed. The day count and deadline come from `kernel.clock` (discovered Sep 10 → day 4 on Sep 14 → Oct 10).
- **AC-22** *Given* "Close as not reportable…" or "Start notification…", *then* the decision needs **two distinct people, one partner and the QI** (`security_admin`), each with a fresh second factor; with one, the drawer reads "Waiting for Margaret Okonkwo"; the agent principal is refused (INV-1); both decisions are logged.
- **AC-23** *Given* timeline entries, *then* they are append-only and attributed; an incident propagated from Accrued (RB-27) shows source "Accrued" and its clock starts at the firm's discovery time; reminders reach the QI and partners at days 20, 25 and 29.

### 5.8 Firm data export (ADM-06b, c, f, g)

- **AC-24** *Given* Felix chooses Export now…, *then* Dialog 460 "Export all firm data?" explains that Margaret must approve and the link expires after 7 days (**b**); after "Request export" the card shows "Waiting for approval · Margaret Okonkwo" and ADM-07 logs "Data export requested by Felix Andersen" (**g**); Margaret's read-only view hides Export now and shows Approve export (**f**); approval needs a fresh second factor and a person other than the requester.
- **AC-25** *Given* the schedule "Monthly · 1st at 2:00 AM CT", *then* it runs only after `security_admin` and a partner have each approved it once (DEC-72), each run notifies both, and the History tray lists Sep 1, 2026 386 GB, Aug 1 371 GB and Jul 1 359 GB with ✓ (**c**).

### 5.9 WISP, residency, retention and support (ADM-06h; support card)

- **AC-26** *Given* fieldset E, *then* Region "United States", AI inference "US only" and Logs & traces "US" show Lock 12 and come from `firms.region` and settings (R-35); fieldset F's rows show the P-14 floors read-only with "Clocks and holds are managed in Files › Retention (FIL-02)." as a planned link until Q-05.
- **AC-27** *Given* fieldset D, *then* the QI, "BH WISP v4 (IRS Pub 5708 format) · approved by Margaret Okonkwo Jan 15, 2026", the annual report dates, "18 of 20 evidenced" with the two open items, training, PTIN attestation and the quarterly access review render from the safeguards record; "Export WISP pack" toasts "WISP evidence pack prepared · 14 documents" and downloads the zip.
- **AC-28** *Given* "Allow support session requests" off, *then* a new support-session request answers 409 `support_requests_disabled` and active sessions keep their expiry; *given* a pending request, *then* `firm_admin` or `security_admin` approves or declines with a fresh second factor, a granted session reads "Granted until 11:40 AM" and can be revoked (SPEC-012 semantics, DEC-72).
- **AC-29** *Given* Margaret (partner, not `security_admin`), *then* the screen is read-only with the T12 banner and locks, Export now is hidden, Approve export is shown (**ADM-06f**).
- **AC-30** *Given* the Posture card, *then* its five lines agree with the fieldsets (SSO enforced; MFA 46/46; US residency; 1 open incident; 2 Pub 4557 items open) and the same endpoint feeds ADM-01's At a glance (G-01) and the M9 checklist.

### 5.10 Read the AI policy (ADM-04a, e, h, i, j)

*As Margaret, the QM owner, I want one versioned policy that names the human approver for every kind of agent output and keeps agents out of what they may not touch, so the firm can show that no AI output was ever approved by the agent.*

- **AC-31** *Given* E0, *then* the header chip reads "BH AI policy v3 · published Jan 14, 2026 by Margaret Okonkwo" and Save as v4… is disabled while the draft equals v3 (**ADM-04a**).
- **AC-32** *Given* fieldset A, *then* twelve rows render from the compiled gate catalogue; each "Default human approver" text matches the roles the permission matrix allows for that gate's actions (generated test); only rows 1 and 5 show policy acceptance, both **Off + Lock 10** with the policy name; the attest column reads "Never" where acceptance exists; the gate popover lists where the gate appears (SHL-10, SHL-11, SHL-12, CLS-07, TAX-09 — planned links where unbuilt) and its log line (**ADM-04i**).
- **AC-33** *Given* Hannah Leclerc (Manager), *then* the banner reads "Only partners can change the AI policy.", every band shows Lock 12, and gates and history still open (**ADM-04e**).
- **AC-34** *Given* Version history, *then* the drawer lists v1 Jan 5, v2 Jan 9 and v3 Jan 14, 2026, each with its diff and publisher and approver (**ADM-04j**).
- **AC-35** *Given* the scrolled view, *then* Auto mode reads Off for EBP audits, FS audits, Reviews & compilations, Preparation, Notices and Advisory and On for Tax returns and Monthly closes on Brightwater Hale (synthetic); on any real firm every Auto mode row reads Off with Lock and the reason "Auto mode isn't available for client data yet" (Season 1 rule, chapter 05 §5.3.12) (**ADM-04h**).

### 5.11 Change and publish the AI policy (ADM-04b, d, g)

- **AC-36** *Given* Margaret steps the override tolerance from 8% to 6%, *then* "Unsaved changes" appears and Save as v4… enables (**b**); Discard reverts to v3; the draft saves with an `If-Match` version and a stale token answers 409 `stale_version`.
- **AC-37** *Given* the Save as v4 sheet, *then* it lists the diff "Override tolerance 8% → 6%", Effective "Sep 15, 2026" and an Approver picker that **excludes Margaret** (DEC-50) (**d**); "Publish v4" requires a fresh second factor and moves v4 to "Awaiting approval · Daniel Reyes"; a C13 human gate appears in Daniel's Approvals with the diff; Daniel approves with a fresh second factor → chip "v4 · effective Sep 15", ADM-07 logs "AI policy v4 published by Margaret Okonkwo · approved by Daniel Reyes" (**g**). The requester approving their own version answers 409 `approver_must_differ`; the agent principal is refused at every step (INV-1).
- **AC-38** *Given* any draft that loosens a locked or default-strict cell (policy acceptance on, §7216 consent off, trace retention under 7 years, autonomy level ≥ 2, Auto mode on for a real firm, `client_drafts_enabled` on, a gate approver wider than the matrix), *then* save answers 422 `policy_loosening_refused` with the field path, and the UI never offers it.
- **AC-39** *Given* v4 published with effective Sep 15, 2026, *then* `agents.api.effective_ai_policy(tenant, type, at)` returns v3 for any `at` before Sep 15 and v4 after, under `kernel.clock`; "Superseded" is derived for display, never stored.
- **AC-40** *Given* `security_admin`, *then* only fieldset D (client data) is editable in the draft; *given* `firm_admin`, *then* the policy is read-only; publication still needs the QM owner and a second partner.

### 5.12 Immediate controls on ADM-04 (new v1 band)

- **AC-41** *Given* Grace (firm admin) with a fresh second factor, *when* Grace turns on "AI on your clients' data" after the disclosure dialog (providers, region, no training, retention and sub-processors generated from the register; which agents run), *then* the opt-in records who, when and the disclosure's register version, exactly as SPEC-036 AC-3; opting out takes effect in the same request; each agent's stage reads "Shadow since …" or "Live since …" and is never promotable from ADM-04 (SPEC-036 Q3).
- **AC-42** *Given* "Pause all agents" by `firm_admin`, `security_admin` or the QM owner, *then* new runs are refused at admission with the existing per-firm pause, a banner names who paused and when, and Resume needs a fresh second factor (ADR P-66).
- **AC-43** *Given* fieldset D's sub-processors, *then* the rows equal the compiled provider-terms register ("Amazon Web Services (Bedrock) · model inference · US"), the model family is named as a model, never as a processor, and no row reads "Anthropic · model inference" (DF-16, DEC-87, RK-39).
- **AC-44** *Given* the §7216 row, *then* it is On + Lock; before T-01 registers C19, the helper reads the T03 empty state; once registered, it lists the blocked clients from the consent gate (Ferris "1 of 2 signed", Stein "declined", Thornbury "not requested" in the seed), matching ADM-05.

### 5.13 Invariants across the epic

- **AC-45 (INV-1)** Every G-02 write action (`ai_policy.draft/publish/approve`, `security.manage`, `session.end`, `staff.unlock`, `incident.decide`, `firm_export.schedule/approve`, `audit_event.export`, `support_session.manage`, `firm_agents.pause`) is denied to the agent and system principals at the matrix, the live-human check and, where a decision table exists, the database CHECK (I-AGENT-NEVER).
- **AC-46 (INV-4)** Every `/v1/firm/*` and `/v1/audit-events*` route answers 404 to client principals; the portal bundle imports no ADM screen.
- **AC-47 (INV-5)** Every G-02 state change writes one audit event naming the person (or "System" for scheduled runs), and ADM-07 renders it with the catalogue verb.
- **AC-48 (dormant policy principal, fixture-only)** *Given* fixture mode, *then* ADM-04c shows "Allow policy acceptance?" with Allow disabled until the attest-client checkbox is ticked, and ADM-04f shows "On · non-attest only" with the within-threshold AJE gate on the policy and the logged toast; *given* any staging or production firm, *then* no route or control reaches either state, every policy-acceptance row reads "Off + Lock" and a draft that turns it on answers 422 `policy_loosening_refused` (AC-38).
- **AC-49 (enterprise identity frames, fixture-only)** *Given* fixture mode, *then* ADM-06 fieldset A shows revision R2's "Require SSO" segmented All users · Per user with "Exceptions — 1 (break-glass account)", IdP-initiated SSO On, the SCIM provisioning rows (Connected · Microsoft Entra ID · 46 of 46 seats · five groups · last sync Today 9:00 AM · 0 errors) and the Posture row "SCIM provisioning on"; ADM-06i lists 46 seat holders with the break-glass account exempt and Locked, and ADM-06j reads "1 user not provisioned · seat limit 46 of 46" with "Open seats (ADM-02) →"; *given* a live firm before G-03-T29, *then* only the single Require SSO toggle renders and no SCIM or per-user route exists.

## 6. Behaviour and flows
**Happy paths** (G-02 §1): Felix enforces SSO, ends a session, opens INC-2026-005 and records a decision that waits for Margaret, and exports Sep 8–14 of the audit log after a fresh second factor. Margaret reads the Copperleaf event's values, changes the override tolerance, requests v4 effective Sep 15, 2026 naming Daniel Reyes, and Daniel approves with a fresh second factor. Grace opts the firm in to AI on client data (SPEC-036).

**State transitions**
| Object | From | Event | To | Who |
|---|---|---|---|---|
| AI policy version | (none) | request publication | `awaiting_approval` | `quality_partner`, fresh MFA |
| AI policy version | `awaiting_approval` | approve | `published` | a different partner, fresh MFA |
| AI policy version | `awaiting_approval` | decline | `declined` | the named approver, fresh MFA |
| AI policy version | `awaiting_approval` | withdraw | `withdrawn` | the requester |
| Audit export | `requested` → `building` → `ready` | job | `ready` | System |
| Audit export | `ready` | download | `downloaded` | the requester, fresh MFA |
| Audit export | `ready`/`downloaded` | 7 days pass | `expired` | System |
| Incident decision | one decider | second, distinct decider | decided | a partner and the QI, fresh MFA each |
| Firm export schedule | `pending_approval` | second approval (other role) | `active` | `security_admin` and a partner |

"Superseded" (policy) is derived, never stored. An audit event is never changed or removed; corrections are new events.

## 7. Domain and data changes
- **`audit_events` (kernel, expand-only; G-02-T06, migration 0172):** `+ ip inet NULL`, `user_agent_family text NULL`, `device_label text NULL`, `session_id uuid NULL`, `auth_method text NULL CHECK IN ('sso','email_code','passkey','totp','support','service')`, `mfa_at timestamptz NULL`, `client_id uuid NULL`, `office_id uuid NULL`; CHECK that the request-context columns are null unless `actor_kind IN ('human','support')`; indexes `(tenant_id, effective_at DESC, seq DESC)`, `(tenant_id, actor_kind, seq DESC)`, `(tenant_id, client_id, seq DESC) WHERE client_id IS NOT NULL`, `(tenant_id, ip) WHERE ip IS NOT NULL`. Insert-only triggers, grants and RLS unchanged; the app role may insert the new columns. The hash chain's leaf moves to version 2 (Q-02 R7; SPEC-341), and version 1 checkpoints keep verifying.
- **Classification:** `ip` and `device_label` are `confidential` personal data: never logged, never in a domain event, masked nowhere because only readers of `audit_event.read` see them. `user_agent_family`, `auth_method`, `session_id`, `mfa_at`, `client_id`, `office_id` are `internal`.
- **Later tables** (their own tasks and migrations): `audit_event_labels`, `audit_exports` (T10), `security_policies`, `auth_session_tenant_revocations` (T14), `firm_export_schedules` (T19), `safeguards_programs`, `safeguards_control_statuses` (T20), `autonomy_policy_drafts`, `autonomy_policy_versions` (T23); shapes in G-02 §4.2.
- **Invariants:** no value of a target is ever written to `audit_events` (DEC-60): `before_ref`/`after_ref` stay identifier-only (`kernel.uow.Ref`); UPDATE and DELETE on `audit_events` stay refused for the app role.
- **Retention:** `audit_event` keeps its 7-year floor (P-14, SPEC-341).

## 8. Interfaces
Three internal contracts, stub first: `docs/contracts/audit-log.md` v1 (G-02-T04), `security-center.md` v1 (T11), `ai-policy.md` v1 (T15). Routes, one matrix action each, as G-02 §4.3. The audit-log family:

| Method | Path | Purpose | Action |
|---|---|---|---|
| GET | `/v1/audit-events` | List with filters, capped counts, `since_seq` | `audit_event.read` |
| GET | `/v1/audit-events/{seq}` | Detail with request context and values section | `audit_event.read` |
| POST | `/v1/audit-events/exports` | Request an export (202) | `audit_event.export` (fresh) |
| GET | `/v1/audit-events/exports/{export_id}` | Export status | `audit_event.export` |
| POST | `/v1/audit-events/exports/{export_id}/link` | 15-minute download link | `audit_event.export` (fresh) |

Module interfaces: `audit_trail.api.list_events`, `get_event`, `events_for_work_item` (T08); `platform.api.register_audit_labeler`, `register_audit_value_resolver` (slots declared in T02, used in T09); `agents.api.effective_ai_policy` (T24).

## 9. Authorisation and tenancy
- **Tenant scoping:** every route through `tenant_session(ctx)`; RLS forced on every new table.
- **Who can do what:** the matrix rows of G-02 §4.4, with `level_in(partner)` written as the derived `firm_partner` role (DEC-132). Every new write action denies `agent` and `system`; every action is unreachable to client principals (404, INV-4).
- **Need-to-know (ADR-024, DEC-60):** `firm_admin` and `security_admin` read audit metadata; values resolve only for a viewer holding the target's content read (`visible()`), so `quality_partner` and `practice_leader` see values `in_scope`.
- **Walls (ADR-026, DEC-43):** walled events are omitted with no hidden count.
- **Client-side access:** none.

## 10. AI behaviour
N/A: no model calls. Agent work appears only as attribution ("‹person› via Agent").

## 11. Integrations
WorkOS (sessions, MFA factors, lock state; Q7 in §20), KMS (export signing, T17), S3 exports bucket with a 7-day lifecycle, Temporal (export, reminders, schedules, indexer). No client system is written to.

## 12. Edge cases and failure modes
- A value resolver that fails or is missing answers `values.status = unavailable` ("Values not available"), never a guess (fail closed).
- A support-session request writes the engineer's request context with `auth_method = 'support'`.
- An agent or system write leaves every request-context column null even when it runs inside an HTTP request.
- Same-minute events order by `seq`; the drawer shows seconds.
- An export whose requester loses `audit_event.export` before download is refused at the link.
- A firm with one partner cannot publish a new policy version (ADR-186 consequences).

## 13. Security and privacy
- **Classification:** request context is personal data (`ip`, `device_label`: confidential). Values in the detail drawer are resolved at read time and masked by classification; a Restricted value is only ever shown masked (`•••-••-2208`).
- **Threats:** value leakage through search, labels and exports (R4); a forged request context (the IP comes from the trusted proxy chain only, `ProxyHeadersMiddleware`); session fixation (the session id is resolved from the current BFF cookie and must belong to the acting user).
- **Mitigations:** generated probe test for a seeded SSN (AC-11), `audit_log.values` off for real firms until pen-test delta #1 closes, fresh MFA on every export and download.

## 14. Audit trail and evidence integrity
Every G-02 state change writes one audit event naming the person, or "System" for scheduled runs (AC-47); the list in G-02 §4.7. `audit_events` stays insert-only and hash-chained; the export manifest carries the P-43 checkpoint.

## 15. Observability
Logs carry codes and identifiers only: never an IP, device label or value. Metrics: export build time, label-index lag, audit list p95.

## 16. Performance and scale
50,000+ events per firm per month at pilot scale; a 50-row page within 500 ms p95 on staging (T10); keyset paging on `seq`; counts capped.

## 17. UX
Screens, states and copy as G-02 §2.1 and §5, verbatim from the handoff with the T03 deviations (DF-17, DEC-35, DF-16, "Values are visible to partners in scope.", the Season 1 Auto mode reason).

## 18. Test plan
| ACs | Suite | Task |
|---|---|---|
| AC-1 to AC-14, AC-45 to AC-47 (ADM-07 parts) | AC suite 1, `backend/tests/contracts/audit_log/` against the stubs, then live | G-02-T05 |
| AC-9, AC-8 (database) | `backend/tests/integration/test_g02_audit_request_context.py` | G-02-T06 |
| AC-15 to AC-30 | AC suite 2 | G-02-T12 |
| AC-31 to AC-44 | AC suite 3 | G-02-T22 |
| AC-48, AC-49 | fixture-mode Vitest | G-02-T13, T16, T25 |
| Seed figures (Day 4 of 30, 18,406, 4 of 1,962, 20,020.00, 46 of 46) | golden tests | G-02-T07 |

## 19. Rollout
- **Flags** (boolean, default off, owner the builder, DEC-55): `audit_log.explorer`, `audit_log.values`, `security_center.v1`, `ai_policy.v1`; created in G-02-T02 and renewed before expiry in the Thu May 13, 2027 train (≤ 90 days, outside Sep 1 – Oct 20).
- **Migrations:** expand-only; the audit request-context migration is reversible (down drops the columns, the CHECK, the indexes and restores the insert grant); up/down/up runs on the local test database, and the staging-copy check is a deploy step.
- **Rollback:** flags off; routes answer 404.

## 20. Open questions
Every other open point in G-02 §11.2 had a recommended answer and is decided in DEC-415.
- [ ] **Q7 (WorkOS capabilities).** Does WorkOS expose (a) clearing a sign-in lock, (b) MFA factors for SSO users, (c) session revocation? No written option: it is a fact to verify against WorkOS (G-02-T14, S10). AC-20's unlock and AC-16's SSO-user count keep the fallbacks of G-02 R8 (timed unlock per DEC-35; IdP attestation) until it is answered. Does not block T01–T07.

## 21. Supersession
| Superseded | By | Closed when |
|---|---|---|
| TASK-042 (red; QD-3): autonomy level and checklist, `PUT /v1/firm/autonomy` | ADR-186; G-02-T23, T24 (`ai_policy.v1` answers 409 `superseded_by_ai_policy` per firm) | AC suite 3 (G-02-T22) merges; closed under QD-3 in G-02-T26 |
| SPEC-024 AC-5 (autonomy stored and audited) | AC-36 to AC-40 (versioned policy) | as above; flag-off firms keep the legacy route and its tests until a superseding SPEC retires it |
| `apps/web/src/screens/Autonomy.tsx` (autonomy and firm-agents cards) | ADM-04 (G-02-T25); the synthetic-only drafted-guidance card (SPEC-035) stays until N-03 | G-02-T25 |
| `apps/web/src/screens/SupportAccess.tsx` (support card) | ADM-06 support card (G-02-T16) | G-02-T16 |
| `GET /v1/firm/audit-events` and `/facets` (SPEC-304, TASK-305; `audit.read`) and `AuditLog.tsx` | `/v1/audit-events*` (G-02-T08) and ADM-07 (G-02-T13) | G-02-T13; the legacy route stays until then |

## 22. Gate check (G-02-T01, 2026-10-26, `origin/main` `bbe1cf37`)
**ADRs.** P-49 and P-08 had no ADR on `main` (the plan's "ADR-148" and "ADR-149" are aliases already taken by P-28 and P-26). Drafted and accepted with the plan's proposed options under the solo amendment: **ADR-186 (P-49, DEC-50 b) accepted**, **ADR-187 (P-08, DEC-53 b) accepted**. No red decision this epic needs is open; the epic is not stopped.

**Q-02 hand-off checklist** (G-02 §8.3):
| Item | State on `main` | Where / ticket |
|---|---|---|
| `audit_events.on_behalf_of_user_id`, `policy_ref`, `engagement_id`, `work_item_id`, `actor_kind` with dormant `policy` | present | migrations 0096, 0108 |
| Hash chain and checkpoints (P-43) | present; schedules not built | `kernel/uow/chain.py`, 0106; Q-02 (schedules) |
| `access_events` | present | Q-02-T20 |
| Retention floors incl. `audit_event` | present as reference data; content per counsel | 0112, `evidence/retention.py`; Q-02-T31 |
| On-demand dual-approval firm export | contract stub only | `evidence/firm_export_contract.py`; Q-02-T43, T47 |
| Incident register, FTC clock, RB-27 propagation | present (create and clock) | `platform/incidents.py`; read side, timeline and decisions are G-02-T18 |
| Staff and portal MFA enforcement | present | `identity/staff_session.py` (no session without MFA), 0133, `fresh-mfa-actions.yaml` |
| TASK-076 opt-in, `agent_stages`, engagement exclusion | present | `identity/routes.py` (`/v1/firm/ai-client-data`), `agents` registry |
| Bedrock provider-terms entry | present | `docs/operations/provider-terms.yaml` |
| Security-suite generators | present | `abacus_tools/codegen/security_tests.py` |

**Cross-epic owners of the revision R2 content:** ADM-04 fieldset F and the fieldset A footer → **K-04** (requested task, S59–S60, before K-04-T21); ADM-04 fieldset G learned-context rows → **K-05** (requested task beside K-05-T10); ADM-04 fieldset G benchmark row and state k → **I-03-T37**; ADM-06 i, j and the R2 fieldset A rows live → **G-03-T29**. Recorded in DEC-415; the requested tasks are for the builder to add to K-04 and K-05's backlogs when those epics open.

**Contract requests** (no issues opened from this branch; the main session opens them at merge): audit-log v1 (G-02-T04, this branch), security-center v1 (G-02-T11), ai-policy v1 (G-02-T15).

## 23. Future / explicitly deferred
Policy principal enablement (≥ Q2 2027, ADR-187); Auto mode enforcement (P-10); SCIM and per-user SSO live (G-03-T29); retention editing (Q-05); support sessions per return (G-04); generated Pub 5708 WISP section (after P-11).
