---
id: SPEC-659
title: W-01 Integration catalogue & Connect — Workbench › Connect (WB-10) and the integration detail and connect drawer (WB-11), C20 v2
status: approved
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-007, ADR-027, ADR-031, ADR-035, ADR-040, ADR-044, ADR-089, ADR-090, ADR-139, ADR-140, ADR-143, ADR-147, ADR-148, ADR-150, ADR-151, ADR-156, ADR-157, ADR-179, ADR-231, ADR-232, ADR-233]
related_specs: [SPEC-020, SPEC-333]
created: 2026-11-15
updated: 2026-11-15
epic: W-01
task: W-01-T01 (TASK-8059)
---

# SPEC-659 · Integration catalogue & Connect (C20 v2)

> **Instructions for coding agents**
> - The design is `docs/plan/epics/W-01.md` §1 to §8; task rows are `docs/plan/epics/W-01.tasks.csv`.
>   The acceptance criteria are the epic's AC-1 to AC-35, adopted verbatim as the spec of record
>   (`docs/plan/epics/W-01.md` §3); this file states each one's testable core and the gate.
> - Screen contracts: `docs/screens/WB-10.md` (a–i) and `docs/screens/WB-11.md` (a–f), W-01-T05.
>   Contract: C20 v2, the v2 section of `docs/contracts/c20-integrations.md` (W-01-T03).
> - **Catalogue honesty** (DEC-46, DF-36, ADR-150): a tile is `available` only when its listing
>   says so, an adapter for its key is registered in this environment, and the firm's kill switch
>   is clear. Everything else is `coming_soon` with Notify me. C20 v1's `catalog.py` already
>   enforces the first two; v2 adds the viewer, the synthetic marker, the kill switch and
>   `published_at ≤ clock.now()`.
> - **Connections stay read-only** (ADR-040, CONN-001): a client always authorises its own ledger
>   in the portal; no firm principal can start a client connection (R1).

## 1. Summary
Workbench › Connect becomes a live, honest catalogue: firm integrations managed by IT/Security or
the firm admin with fresh MFA, personal "acting as you" integrations for any user, and a
read-only view of client-authorised connections. One drawer per integration says how it
authenticates, what Accrued may read, write and never do, its health, the agents that depend on
it and who can use it. A token expiry becomes "Needs reauth", notifies IT once, and blocks
dependent agent runs at admission until a person reconnects. No new real connector.

## 2. Gate check (main ae0055816, 2026-11-15; DEC-5044)

| P-ID / decision | Subject | On main | State | What W-01 does |
|---|---|---|---|---|
| P-17 (DEC-46) | `integrations` module, write-capability framework | ADR-150 | accepted | Red module; data-driven catalogue; honesty; declared writes only |
| P-18 (DEC-49) | Tax-engine integration, never transmit | none of its own; DEC-49 and ADR-231 §6 bind it | not drafted | CCH Axcess Tax in file-bridge mode renders "File bridge" (AC-23) |
| DEC-70, DEC-17 | First live ledger; vendor applications | ch09 rows | decided | QBO is the one real client-authorised adapter; no real personal Google/Microsoft adapter |
| DEC-08 · P-34 | Status vocabulary | `status-vocabulary.yaml` `integration` | in place (C20 v1) | v2 adds the viewer-relative words (W-01-T02) |
| P-36 · P-39 · P-05 | API conventions · per-module registries · module map | ADR-139 · ADR-140 | accepted | Envelope with counts; per-module files; the `agents → integrations` edge (T02) |
| P-10 (DEC-21) | Role catalogue | ADR-147 | accepted | `security_admin` and `firm_admin` hold firm connect and disconnect with fresh MFA |
| P-37 (DEC-27) | Clock, synthetic marker | ADR-143 | accepted | `firms.synthetic` gates fake adapters; `published_at` against the clock |
| P-22 (DEC-41) | Agent model | ADR-233 | **proposed** (acceptance: Ayush) | `requires_integrations` on the capability spec (T14) |
| P-28 (DEC-55) | Entitlements and flags | ADR-148 | accepted | Two rollout flags; no Connect entitlement |
| P-29 (DEC-68) | Busy season | ADR-151 | **proposed** | Window rules; flags expire outside the window |
| P-14 · P-65 · P-66 | Retention · tenant keys · kill switches | ADR-179 · ADR-156 · ADR-157 | **proposed** | `integration_event` record type; sealed secrets deleted on disconnect; "Paused" |
| P-15 | SSE | ADR-232 | proposed (not gating) | Polling baseline; SSE optional |
| DF-36 · DF-34 · DF-35 | Catalogue hygiene · seed · kit data | ch09 rows | decided | Canvas list wins; "Connected by Felix Andersen · Jan 14, 2026 9:12 AM"; no kit text |

**C20 v2 issue (the plan's Contract Monday item):** C20 v1 (A-02) delivered `integration_catalog`
(with honesty, consent copy, scopes, the operator load function), `firm_integrations` (token and
file-bridge modes), sealed `integration_secrets` and `integration_mappings`. v2 is additive:
catalogue columns for the workbench (categories, description, auth line, published_at), wider
install statuses and modes (`firm_app`), `user_integrations`, OAuth states, `integration_events`,
`integration_interest`, `integration_catalog_imports`, and the secrets owner CHECK (W-01-T04).
The plan's AC "ADR-136 (P-17) is Accepted" reads ADR-150 on this repository.

**Red rows open:** P-22, P-29, P-14, P-65, P-66 proposed; built on per AMENDMENT-solo (DEC-5044).

## 3. Open questions (epic §11.2) — the recommended answers (DEC-5044)
OQ-1 both `security_admin` and `firm_admin` enable firm integrations, with fresh MFA · OQ-2 the
POR-16 client feeds are catalogue rows with `surfaces = ['portal']`, never counted in WB-10 · OQ-3
CCH in file-bridge mode reads "Auth mode — File bridge · a person exports and imports", no token
row, no Reconnect · OQ-4 declared-but-off writes show Lock and "Off for this firm"; unregistered
ones are dropped · OQ-5 disabling a client-authorised firm app suspends the firm's client
connections for that provider and blocks new POR-16 starts · OQ-6 every firm staff role sees
client companies, filtered by `visible()` and walls, no hidden counts · OQ-7 15-minute ticks,
three transient failures to Needs attention, 401/`invalid_grant`/`token_expired` to Needs reauth
at once · OQ-8 imports by the platform operator through the ops task; production imports name
both founders · OQ-9 a killed integration reads "Paused", Reconnect hidden · OQ-10 canary before
the window, real firms after it.

## 4. Scope
Two screens (WB-10 a–i, WB-11 a–f). Modules: `integrations` (red), `connections` (red, additive),
`agents` (red, admission precondition), `tax` (amber, linked-records provider), `notifications`
(amber). Flags: `integrations.connect_v1`, `integrations.health_monitor` (W-01-T02). Setting:
`integrations_fake_adapters` (refused at boot in production). Out of scope: any new real
connector, write execution, ADM-08 and ADM-09 internals, POR-16 UI beyond the flag-gated firm-app
check, a catalogue editor screen, token-expiry pre-warnings, SCIM, palette search.

## 5. Acceptance criteria (epic §3, verbatim there)
Criterion ids: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24, AC-25, AC-26, AC-27, AC-28, AC-29, AC-30, AC-31, AC-32, AC-33, AC-34, AC-35.
- **AC-1 to AC-5** Honest catalogue: 53 = 9 + 38 + 6 at E0 with the nine connected tiles; category, status and search filters keep catalogue-total category counts; 55 = 9 + 40 + 6 at E2 (Drata, Vanta); honesty enumerated against registered adapters; no vendor logo, kit text or payment copy.
- **AC-6 to AC-9** Roles: non-admin firm tiles `aria-disabled` with the managing person's name; firm connect and disconnect `security_admin`/`firm_admin` with fresh MFA (403 `mfa_required`, `max_age_s = 900`); the agent denied every integration action; portal principals 404; managed-by resolved at read time.
- **AC-10 to AC-13** Personal connect: consent card from `consent_copy` v1; single-use hashed state, 10-minute expiry, PKCE; 409 `invalid_state` / `connect_declined`; membership end disconnects and deletes secrets.
- **AC-14 to AC-16** Firm reconnect: Needs reauth on the Aug 17 replay; Reconnect with fresh MFA; computed "paused"; prerequisite scope 409 `prerequisite_scope_missing`; firm-app enable.
- **AC-17 to AC-19** Client-authorised: "Firm app · each client authorizes its own company"; client companies through `connections.api` with walls; no client-connect route (R1).
- **AC-20 to AC-23** Detail: Connection card, Read 4 · Write 2 · Never 1, five events, five agents, who can use it; writes joined with `write-capabilities.yaml`; read-time labels; file-bridge rendering.
- **AC-24 to AC-26** Disconnect: typed name (422 `confirm_name_mismatch`), `seen_version` (409 `stale_version`), fresh MFA, secret deleted, best-effort remote revoke; firm-app disable suspends client connections; personal disconnect self only.
- **AC-27 to AC-30** Health monitor and admission: transitions with events and outbox; one `connection_needs_reauth` per recipient; admission refuses `integration_reauth_required` / `integration_not_connected` / `integration_paused`; replay history; silenced by `integrations.health_monitor`.
- **AC-31 to AC-33** Notify me; operator-only catalogue import with dry run and log; `integration_available` fan-out.
- **AC-34 to AC-35** The live path is unchanged with `integrations.connect_v1` off; live-path merges before the window; the migration is expand-only.

## 6. Task map
S45: T01 this SPEC · T02 protected bundle (red) · T03 C20 v2 stub · T04 migration (red) · T05
screen contracts · T06 ADR-078 AC suite 1 and consumer tests. S46–S48 as the epic's §9.

## 7. Deviations
As the epic's §2.1 notes and WB-11's deviations (file bridge, Off for this firm, planned links,
MCP count), recorded in the screen contracts (W-01-T05).
