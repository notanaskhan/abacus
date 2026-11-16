---
id: SPEC-680
title: G-04 Platform console, plan & usage and support — the Accrued tenant console (PLT-01), Firm settings › Plan & usage (ADM-14) and the Support panel (SHL-05)
status: approved
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-007, ADR-014, ADR-024, ADR-027, ADR-031, ADR-089, ADR-090, ADR-139, ADR-140, ADR-141, ADR-142, ADR-145, ADR-147, ADR-148, ADR-151, ADR-165, ADR-300]
related_specs: [SPEC-007, SPEC-012, SPEC-681]
created: 2026-11-15
updated: 2026-11-15
epic: G-04
task: G-04-T01 (TASK-8200)
---

# SPEC-680 · Platform console, plan & usage and support

> **Instructions for coding agents**
> - The design is `docs/plan/epics/G-04.md` §1 to §8; task rows are `docs/plan/epics/G-04.tasks.csv`.
>   The acceptance criteria are the epic's AC-1 to AC-13 and AC-26 to AC-58 plus INV-1 to INV-5,
>   adopted verbatim as the spec of record (`docs/plan/epics/G-04.md` §3); this file states each
>   one's testable core, the gate and the decisions. Support sessions (AC-14 to AC-25) are
>   SPEC-681, which amends SPEC-012.
> - Screen contracts: `docs/screens/PLT-01.md`, `ADM-14.md`, `SHL-05.md` (G-04-T06). Contracts:
>   `docs/contracts/platform-console.md`, `plan-usage.md`, `support.md` (G-04-T03).
> - **Never** a price, an overage amount, a payment or an invoice (P-27, D5). **Never** a client,
>   contact, engagement or document name in a console payload (AC-2). **No agent action** on any
>   G-04 surface (INV-1). Agent-minutes are stored integers summed by code (ADR-050, ADR-148).

## 1. Summary
Accrued staff provision tenants and change entitlements in a staff console instead of the CLI.
Each firm sees its plan and agent-minute usage, decides who is warned and what happens at 100%,
and asks for more through a partner-approved request. Every firm user gets an in-app Support
drawer with a named human, help articles and system status. No billing, no prices, no payments.

## 2. Gate check (main 47a3b87fe, 2026-11-15; DEC-5200)

| P-ID / decision | Subject | On main | State | What G-04 does |
|---|---|---|---|---|
| P-28 (DEC-51, DEC-55) | Entitlements, agent-minutes, two-layer budgets | ADR-148 | accepted | `plan_entitlements` versions; usage from P-10's ledger; At 100% policy; USD layer untouched |
| DEC-72 | Firm export and support sessions | ch09 row | decided (red, counsel) | SPEC-681; OQ-1 removes the emergency carve-out |
| P-62 (DEC-76) | Platform reference data, two-person publish | ADR-300 | accepted | Publications queue wraps K-02's owner-only definer publish (T10) |
| P-27 (DEC-89) | Payments and billing boundary | no ADR on this repository; DEC-89 binds it | decided | No price, payment or invoice; overage copy carries no amount |
| P-55 (DEC-03) | AWS topology and regions | ADR-142 | accepted | Region pinned at provisioning; only `live` regions selectable |
| P-54 (DEC-22) | Authentication, staff issuer | ADR-141, ADR-165 | accepted | Console on the staff issuer with staff MFA |
| P-10 (DEC-20, DEC-21) | Role catalogue, need-to-know | ADR-147 | accepted | `security_admin` approves sessions, never sees Plan & seats; partner level approves plan requests |
| P-06 | Generalised `visible()` | ADR-145 | accepted | A support scope kind (SPEC-681) |
| P-29 (DEC-68) | Busy-season change policy | ADR-151 | accepted | Flags expire outside the window; live-path edits before Thu Aug 24, 2028 |
| P-36 · P-05 · P-39 | API conventions · module map · per-module registries | ADR-139 · ADR-137 · ADR-140 | accepted | Envelope with `counts`; per-module matrix and flag files; 501 stubs |
| DEC-32 | Undesigned screens | ch09 row | decided | Console sections composed from kits (T17) |
| DF-31 | Status vocabulary additions | ch09 row | decided | G-04's rows in the protected bundle (T02) |
| DEC-60 · DEC-61 · DEC-43 | Audit content · notification rows · walls | ch09 rows | decided | Identifiers only; no message bodies; walls 404 with no hidden counts |

**Upstream on main:** F-03-T28 (`plans`, per-module `tenant_entitlements`, `require_entitlement`,
migration 0088, widened through 0880) done; P-10-T06 (`agent_minute_ledger`, `usage_month` as a
`YYYY-MM` label, `engagement_agent_budgets`, migration 0684) and P-10-T42 (`GET /v1/firm/usage`)
in review; K-02-T03 (reference-set definer publish) in review; contracts C2 and C16 on main.
P-01-T04 already added `firms.sandbox_of_firm_id` (migration 0091), so SPEC-681's identity
migration does not.

**The `plan_entitlements` gate (the epic's naming note; Q-03-T318).** No `plan_entitlements`
table exists: migration 0107 only defines the function `apply_plan_entitlements`, which writes
`tenant_entitlements` module rows at provisioning. F-03's entitlement pieces (`plans`,
`tenant_entitlements`, `require_entitlement`, `/v1/me` entitlements) are all present, so the
call-off row Q-03-T318 does not trigger: G-04 proceeds without taking scope from its backlog.
G-04-T04 creates `plan_entitlements` with `usage_month_anchor_day`. P-10's `usage_month` stays
the label of the month in which a usage window starts; the anchor day maps it to the window
(Brightwater: anchor 15, `2026-09` = Sep 15 – Oct 14).

**Red rows open:** none of the gating ADRs is proposed. DEC-72 never defaults on silence; OQ-1
takes the epic's recommended answer under AMENDMENT-solo, and Ayush accepts it here (DEC-5200).

## 3. Contract issues (the plan's Contract Monday items)
1. **Platform console** (`docs/contracts/platform-console.md`, G-04-T03): staff routes under
   `/v1/platform/*` on the staff issuer; two staff roles from the staff token's claims; the
   metadata-only directory fields; provisioning through `TenantProvisioningWorkflow`
   (`workflow.patched("g04_plan_v2")`); regions; cross-tenant support sessions (scope kind only);
   the plan-request inbox.
2. **Plan & usage** (`docs/contracts/plan-usage.md`): `GET /v1/firm/plan`, billing contact,
   budget alerts with `version`, engagement budgets through `visible()`, billing rates or
   `{connected:false}`, plan requests with the C13 gate kind, the additive `GET /v1/firm/usage`
   fields and the in-process read `platform.api.over_limit_policy(tenant)`.
3. **Support** (`docs/contracts/support.md`): the caller's conversation with computed
   availability, messages, help articles (list, search, read), firm-facing status, and the
   support-session v2 fields of SPEC-681.

## 4. Open questions (epic §11.2) — the recommended answers (DEC-5200)
OQ-1 the emergency carve-out is removed; no HTTP route or console control creates a staff-approved
session (SPEC-681) · OQ-2 only `trigger_kind = schedule` pauses under "Pause scheduled agents
only" · OQ-3 in-house chat and help, no vendor, no new sub-processor · OQ-4 a platform admin's
entitlement change shows in the firm's trail as actor kind `support`, "Rowan Achebe (Accrued)";
no new actor kind · OQ-5 support messages kept 3 years after the conversation closes, registered
with the retention registry at S50 · OQ-6 service-line modules are recorded and displayed, not
enforced, in 2028 · OQ-7 both PLT-01b and ADM-14e list every held module (six for Brightwater),
a design follow-up in the screen contracts · OQ-8 one configured partner approver on
`usage_alert_policies` (default the managing partner), any partner-level member as fallback,
never the requester · OQ-9 K-05 registers a publication kind against `PlatformOpsWorkflow`.

**Role naming (DEC-5201).** The epic's console staff roles are `platform_admin` and
`platform_support`. `platform_support` is already SPEC-012's break-glass session role (the
`firm_role` of a support context, `identity/context.py`), so the console's support role is
`platform_support_desk` in the matrix. Staff roles are carried by the staff token's claims and
are never a firm membership role; firm and portal principals never hold them.

## 5. Scope
Three screens (PLT-01 a–d, f, g live and e fixture-only; ADM-14 a–f; SHL-05 a–f, d′). Modules:
`identity` (red; SPEC-681, the platform principal), `agents` (red; the admission over-limit hook),
`platform` (amber; plan, alerts, plan requests, billing rates, console, directory, support chat,
help, status, publications), `notifications` (amber; C16 kinds), `workbench` (amber; a read-only
`active_users`). Flags: `platform.console` (global), `platform.plan_usage` and `support.panel_v2`
(per firm), all default off; on this repository's calendar they are created 2026-11-15 and
expire 2027-05-13 under DEC-137's override (the plan's 2028-11-08 is the plan calendar). Setting: `platform_fake_providers` (refused at boot in production).
Out of scope: epic §2.3 (live Library releases, Teach mode, live billing rates, engagement
overrides, service-line enforcement, chat attachments, a vendor, automated status, an authoring
UI, prices, EU and UK regions, the emergency approval, a "Share with support" control).

## 6. Acceptance criteria (epic §3, verbatim there)
Criterion ids: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-26, AC-27, AC-28, AC-29, AC-30, AC-31, AC-32, AC-33, AC-34, AC-35, AC-36, AC-37, AC-38, AC-39, AC-40, AC-41, AC-42, AC-43, AC-44, AC-45, AC-46, AC-47, AC-48, AC-49, AC-50, AC-51, AC-52, AC-53, AC-54, AC-55, AC-56, AC-57, AC-58, INV-1, INV-2, INV-3, INV-4, INV-5.
- **AC-1 to AC-5** Directory: six tenants, tiles 6 = 4 + 1 + 1 and "404 of 490" (sandbox excluded); a generated OpenAPI lint and fixture scan prove metadata only; server-side filters with tile `counts` ignoring the tile filter; health from W-01 health and open incidents; regions from `platform_regions` content.
- **AC-6 to AC-9** Drawer and entitlements: the Brightwater drawer facts; seats 46 → 48 with a 20–500 character reason and staff MFA within 15 minutes writes `tenant.entitlements_changed` to both logs and a new `plan_entitlements` version; 422 without a reason, 403 for `platform_support_desk`; 409 `seats_below_used`; region never editable; policy principal is a necessary condition only.
- **AC-10 to AC-13** Provisioning: 202 with a workflow id and `Idempotency-Key`; `g04_plan_v2` activities and two first-admin invitations (`firm_admin`, `security_admin`); `tenant.provisioned`; replays return the same workflow; 422 `region_not_live`; 409 `tenant_code_taken`; training sandbox (cut item 3).
- **AC-26 to AC-32** Plan & usage read: the Oct 1 meter (14,920 = 8,640 + 4,610 + 1,420 + 120 + 130 of 20,000), Plan & seats, billing rates (fake provider for synthetic firms only, else not connected), modules, partner read-only and `security_admin` hidden, the copy lint, engagement rows through `visible()`.
- **AC-33 to AC-39** Alerts and At 100%: seeded rules; save with fresh MFA and `version` (409 `stale_version`); exactly one alert per rule and usage month; the over banner with no amount; the admission hook refuses only `schedule` runs with `budget_100pct`; one engagement alert per usage month; the firm default only.
- **AC-40 to AC-43** Request more: `awaiting_partner` with a C13 gate; partner level, fresh MFA, not the requester (409 `plan_request_self_approval`); `sent_to_accrued`, `applied` through `mark-applied`; ADM-01's Add seats is the same request.
- **AC-44 to AC-49** Chat: one thread per user (OWN); availability from support hours content and a 5-sample median; plain text 1–4,000, 30 per 10 minutes, `confidential`, never logged; content-free reply email after 5 minutes unread; suggestion cards; no model reads or writes support messages.
- **AC-50 to AC-52** Help: context group from the screen ID, server-side full-text search, structured blocks only, two-person publish (`approver_is_drafter`), immutable versions.
- **AC-53 to AC-56** Status: core plus the firm's installed integration components, worst of global incidents and W-01 health, region line; staff post and resolve incidents (≤ 280 characters, no firm or client name); only connectors that exist.
- **AC-57 to AC-58** Publications: two-person publish with fresh MFA through a worker activity calling K-02's owner-only definer; no migration or deploy.
- **INV-1 to INV-5** The agent is denied every G-04 action (generated tests); INV-2 vacuous; walls hold; portal principals hold no G-04 action and SHL-05 is not mounted in the portal; attribution strings as the epic gives them.

## 7. Task map
S47: T01 this SPEC and SPEC-681 · T02 protected bundle (red) · T03 contract stubs (red) · T04
platform migration (red) · T05 SPEC-012 amendment in identity (red) · T06 screen contracts · T07
ADR-078 AC suite 1. S48–S51 as the epic's §9 (T08 to T22).

## 8. Deviations
As the epic's §2.1 notes (read-only Stable channel row, PLT-01e fixture-only, PLT-01c's viewer,
region labels as content, the omitted chat paperclip, modules 4 vs 6), recorded with decisions in
the screen contracts (G-04-T06).
