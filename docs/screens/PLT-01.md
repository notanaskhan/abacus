# PLT-01 · Accrued tenant console

| Field | Value |
|---|---|
| Route and params | console entry `apps/web/console.html` (third Vite entry, chapter 04 §1.1): `/tenants`, `?ov=tenant:<code>` (drawer O2 480), `/tenants/new` (O6 wizard), `?sheet=support-session:<code>` (O3), `/regions`, `/library` (fixture-only), `/support-sessions`, `/status`, `/support`, `/publications` |
| Template and host frame | T1 platform variant of the shell + O2 drawer 480 + O6 wizard + O3 sheet; toast |
| Surface | console (staff issuer only; never the firm or portal build) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/PLT-01 Accrued tenant console/` (no `revision.md`) |
| Epic and tasks | G-04 · SPEC-680 AC-1 to AC-13, SPEC-681 AC-15, AC-17 · G-04-T06 (contract), T03 (stub and typed fixtures), T09 (API), T13 (scenarios), T14 (screen), T17 (undesigned sections), T21 (parity) |
| Persona | Rowan Achebe (Accrued platform admin); Jordan Pryce (Accrued Support) on d |
| Flags | `platform.console` |
| Priority | P2 |
| Manifest status | planned |
| Owner | notanaskhan (build, Track 1 lane rule); ayushkbhatia (design fidelity) |

## States

7 artboards: a–d, f, g live; e fixture-only until W-03 (DV-1).

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Tenants | 6 rows (Brightwater Hale LLP, its Training sandbox, Tidewell Rourke & Co. LLP, Kessling Mott LLP, Ostrander Pike CPAs, Ainsley Ward Partners); tiles 6 = 4 Healthy + 1 Degraded + 1 Onboarding and "404 of 490"; footer "Seats used 46 + 128 + 212 + 18 + 0 = 404 of 490 provisioned (sandbox excluded)." (computed, `platform/g04_fixtures.py`) | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · **C locked** | planned · `plt01.a` |
| b | Tenant drawer · Brightwater Hale | Modules (four service lines; DV-5), Seats 46 ⇕, Renewal Jan 1, 2027, Region United States + Lock "Storage Ohio, backup Oregon; inference US", Library channel "Stable" read-only + Lock (DV-2), Policy principal toggle with "The firm decides in its AI policy; currently off.", Teach mode "Coming soon"; Support access with the Aug 17, 2026 history row (Integration settings only · approved by Felix Andersen 10:12 AM · closed 11:40 AM, green-tint "Closed") | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · **C locked** | planned · `plt01.b` |
| c | Provision tenant… · Review | O6 Firm · Region · Modules & seats · First admins · Review for Ainsley Ward Partners: United States (EU and UK "Planned", DV-4), Tax and Client accounting, 64 seats, Firm Admin + IT/Security first admins; dark "Create tenant" (DV-3) | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · **C locked** | planned · `plt01.c` |
| d | Support session request · Kessling Mott | O3 sheet: Requested by Jordan Pryce · Reason "Tax-engine sync latency since Sep 12" · Scope "Integration settings and sync logs only" ⇕ · Duration "2 hours" ⇕ · amber "Awaiting firm approval (Kessling Mott IT/Security)"; **no approve control** (SPEC-681 AC-15) | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · **C locked** | planned · `plt01.d` |
| e | Library releases | Stable · 2026.9 · 28 agents on five tenants; Early access · 2026.10-rc1 · 30 agents on one; "Promote to Stable…" (two Accrued approvers) | Mon Sep 14, 2026, 9:24 AM CT | E0 | C (report only) | planned · `plt01.e` (fixture-only, DV-1) |
| f | Regions | United States "Live"; European Union and United Kingdom "Planned" with labels from `platform_regions` content (DV-4) | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · **C locked** | planned · `plt01.f` |
| g | Tenant created | toast "Tenant created · invites sent to 2 first admins"; the new row tinted until the next load; Health "Onboarding · first admin invited" (added during the build; not in the spec's STATES list) | Mon Sep 14, 2026, 9:24 AM CT | E0 + provisioned | D · **C locked** | planned · `plt01.g` |
| loading | — | skeleton after 200 ms (T1 grammar) | — | — | D | planned |
| error | — | the directory read failed: designed error with Retry | — | — | D | planned |
| not allowed | — | `platform_support_desk` on provision or entitlement edits: controls disabled with the reason; any firm or portal token: the console host never serves it | — | — | — | planned |
| flag off | — | `platform.console` off: staff routes answer 404; the console runs on fixtures only | — | — | — | planned |

Undesigned sections (DEC-32, composed from kits with Ayush's one-day review, G-04-T17): Support sessions list, Status (incidents with post and resolve sheet), Support queue drawer on the ChatThread kit, Publications queue, Plan requests tile and drawer card, "Create training sandbox…". Fixture scenarios: `apps/web/src/fixtures/scenarios/console.ts` (G-04-T13) from the typed fixtures; copy keys `plt01.<state>.<element>`.

## API

`docs/contracts/platform-console.md`: `GET /v1/platform/tenants*`, `PATCH …/entitlements`, `POST /v1/platform/tenants`, `…/sandbox`, `GET /v1/platform/provisioning/{id}`, `GET /v1/platform/regions`, `GET /v1/platform/support-sessions`, `GET /v1/platform/plan-requests` · `…/mark-applied`; `POST /v1/support/sessions` (SPEC-681). Staff actions (`platform_tenant.*`, `platform_entitlements.update`; DEC-5202) on the staff token; metadata only (AC-2).

## Links

| From | To | Status |
|---|---|---|
| Health pill | Status section on the incident | planned (T17) |
| Support cell | O3 request sheet or its history | planned (T14) |
| Request support session… | the firm's ADM-06 request | live after T05 |
| Library releases nav | PLT-01e | hidden in production until W-03 (DV-1) |

## Notes

The only product chrome with the Accrued mark (DF-41, G-D11): 20 px monogram plus a "Console" pill; nav Tenants · Regions · Library releases · Support sessions · Status; "Support queue" pill, bell, "RA". Staff SSO, staff MFA and a WAF IP allowlist (T22). The console never shows a client name, never offers "View as firm" or "Open client data", and never carries the firm's brand.

## Deviations

| ID | Deviation | Decision | Owner |
|---|---|---|---|
| DV-1 | PLT-01e Library releases is fixture-only: scenario and Tier C report now; the nav item is hidden in production until W-03 makes it live on the agent library | DEC-5206 (epic §2.3) | notanaskhan (W-03) |
| DV-2 | The drawer's Library channel row is read-only "Stable" with a Lock until a library with channels exists (W-03); the design's "Stable ⇕" picker is not built | DEC-5206 | notanaskhan |
| DV-3 | PLT-01c's README viewer "Ainsley Ward" is read as Rowan Achebe running the wizard for Ainsley Ward Partners | DEC-5206 | ayushkbhatia |
| DV-4 | Region "Planned" labels are `platform_regions` content rows, not code; the design's "Planned 2027" is stale in 2028 and the fixture keeps it | DEC-5206 | ayushkbhatia (T20 content) |
| DV-5 | Modules list every held module (OQ-7): PLT-01b's four for Brightwater and ADM-14e's six differ in the handoff; both screens list all held modules; a design follow-up | DEC-5200 OQ-7 | ayushkbhatia |
| DV-6 | The billing-rate provider and the policy principal are availability facts only: "Policy principal available" never accepts a policy (P-08 dormant, AC-9) | DEC-5206 | notanaskhan |

## Acceptance

SPEC-680 AC-1 to AC-13 and SPEC-681 AC-15, AC-17 for this screen; each becomes a test named "PLT-01 acceptance: <criterion>". Design-fidelity sign-off: Ayush.
