# ADM-07 · Audit log explorer

| Field | Value |
|---|---|
| Route and params | `/settings/audit-log` behind `audit_log.explorer` (G-02 §5.1). `?actor=via_agent&object=&action=&from=&to=&office=&ip=&q=`; `?event=<seq>` opens the O2 drawer; `?target=<type>:<id>` pre-filters (used by ADM-03, ADM-04, ADM-06) |
| Template and host frame | T1 index inside the T12 frame (cch-sync Activity feed grammar), section "Audit log"; FilterChips, Pane, SearchField, Timeline with markers, Tag, O2 drawer 480 with KVRow and DataTable, Dialog 440, EmptyState, Toast |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ADM-07 Audit log explorer/` (README.md, spec.md; no revision) |
| Epic and tasks | G-02 · contract stub T04 (TASK-1291) · AC suite T05 (TASK-1292) · request context T06 (TASK-1293) · seed T07 (TASK-1294) · read service T08 · value resolution T09 · label index T10 · screen T13 · export T17 · parity and journeys T21 · this contract T03 |
| Manifest status | planned (`routes/manifest/adm.ts`): built by G-02-T13 behind `audit_log.explorer` |

Code (G-02-T13): `apps/web/src/screens/ADM-07/{index.tsx, scenarios.ts, copy.ts, ADM-07.test.tsx}`, `apps/web/src/domain/audit/{queries.ts, catalogue.ts}`; fixtures `src/fixtures/seed/audit-log.ts`, `handlers/audit-log.ts`, `scenarios/ADM-07.ts` (TASK-1291).

## States

7 artboards (a–g).

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Owner · status |
|---|---|---|---|---|---|
| a | felix-andersen (IT / Security) | Mon Sep 14, 2026, 9:24 AM CT | E0 | past 7 days, 14 rows, "18,406 events · immutable", note "Policy principal: 0 events — policy acceptance is off (AI policy v3)." | G-02-T13 · fixture (all 14 rows); staging asserts the built producers' rows (G-02 §5.4) |
| b | felix-andersen | 9:24 AM | E0 | Actor "via Agent": rows 6, 9, 11, 14; chip amber-tint; "4 of 1,962" | G-02-T13 · fixture + staging |
| c | **margaret-okonkwo** (values) and felix-andersen (values withheld) | 9:24 AM; detail 9:18:42 AM | E0 | `?event=<Copperleaf seq>`: O2 drawer, actor, authority, time to the second, IP / device, session, content hash, before → after, Not included, Source, "Immutable. Corrections are new events." | G-02-T13, T09 · fixture (staging uses a built target type) |
| d | felix-andersen | Sep 14, 9:18 AM | E0 + dormant policy | Policy principal on: "Entries accepted by Policy: BH AJE thresholds v2" and "Acceptance reversed by Priya Raman"; note "2 events" | G-02-T13 · **fixture only** (dormant P-08; live with C-02) |
| e | felix-andersen | 9:24 AM | E0 | Export… Dialog 440: Sep 8–14, 2026, CSV + signed JSON manifest, include before/after On | G-02-T13, T17 · fixture + staging |
| f | felix-andersen | 9:24 AM | E0 | search "pell street iii": "No events match 'pell street iii'." / "Search covers actors, objects and details." | G-02-T13, T10 · fixture + staging |
| g | felix-andersen | 9:24 AM | E0 | after e: toast "Export ready · SHA-256 manifest included"; file and manifest | G-02-T13, T17 · fixture + staging |

**New v1 frames (G-02-T03 revision; built by T13):** the values-withheld state (c for a reader without the target's content read: "Values are visible to partners in scope."), registered planned links for unbuilt targets ("Run ›" → WB-09, object chips → CLS-07, TAX-09, SIG-01), and the request-context columns shown only to firm admin, security admin and quality partner (DEC-420).

Non-artboard states: loading (rows skeleton), error, not-allowed (client 404; agent, system and refused readers 403), flag off (route absent; the legacy explorer `GET /v1/firm/audit-events` unchanged), values unavailable ("Values unavailable" when a resolver is not registered).

## API

| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons |
|---|---|---|---|---|
| read | `GET /v1/audit-events` | list envelope; filters actor_kind, actor_id, object_type, action, from, to, office_id, ip, q, since_seq; counts capped | `audit_event.read` | per event through `visible()`; walls omit events with no hidden count (DEC-43) |
| read | `GET /v1/audit-events/{seq}` | authority, time to the second, request context (three roles only), content hash, `values {status: resolved, withheld, unavailable}`, not_included, source | `audit_event.read` | values resolved at read time and masked (DEC-60) |
| write | `POST /v1/audit-events/exports` | `{from, to, filter, include_values}` → 202 `{id}`; `Idempotency-Key` | `audit_event.export` (fresh) | `security_admin` |
| read | `GET /v1/audit-events/exports/{id}` | status, row count, digest | `audit_export.read` | — |
| write | `POST /v1/audit-events/exports/{id}/link` | 15-minute presigned link; audited download | `audit_event.export` (fresh) | `security_admin` |

Contract: `docs/contracts/audit-log.md` v1 (stub, TASK-1291; DEC-417, DEC-420). No route changes or removes an event.

## Status

Markers: ok (filled check: approvals and sign-offs by a named person or, in d, a named policy), no (filled ✕: reversals, removals), pl (plain glyph: neutral). Actor-type tags: Person · via Agent (atom glyph) · Policy (Scale glyph, d only) · System.

## Copy

Verbatim from the handoff spec via `copy.ts` (the SPA composes titles from action codes and facts: P-34). Count "18,406 events · immutable"; note "Policy principal: 0 events — policy acceptance is off (AI policy v3)."; footer "Showing 14 of 18,406 · Load more"; drawer footer "Immutable. Corrections are new events."; withheld reason "Values are visible to partners in scope."

## Links

| From | To (manifest builder) | Planned or live |
|---|---|---|
| Settings navigation rail: Settings home · Offices & teams · Security · AI policy · Consents · Developer · Integrations · Portal · Quality · Monitoring · Inbox · Run history · Review · Ridgeline · BH AJE thresholds v2 | ADM-01 · ADM-03 · ADM-06 · ADM-04 · ADM-05 · ADM-09 · ADM-08 · ADM-10 · ADM-11 · ADM-12 · INB-01 · WB-08 · TXP-02 · KNW-04 | live where built, as ADM-01's section rows; "not built yet" in dev and fixture builds, hidden in production (ED-113) |
| "Run ›" | WB-09 (P-09) | planned |
| object chips | AUD-02 (live), CLS-07 (C-01), TAX-09 (T-01), SIG-01 (N-02), CLI-02 (live), WB-01 (W-03) | mixed |
| actor names | ADM-02 user drawer | live |
| IP | this screen filtered by IP | live |
| engagement-filtered view | AUD-29 (P-05) | planned |

## Acceptance

- ADM-07 acceptance: row grammar matches the cch-sync Activity feed (76px when column, 20px markers, 13.5/500 titles, 12.5 ink-2 details, hairline rail, each row's own date over its time).
- ADM-07 acceptance: every approval row names a person; agent rows read "‹person› via Agent"; the policy variant reads "Policy: BH AJE thresholds v2"; never "Accrued Agent".
- ADM-07 acceptance: the Copperleaf batch foots: 11,860 + 700 + 2,140 + 5,320 = 20,020; the 14,900 entry stays "Review required" for Priya Raman.
- ADM-07 acceptance: events agree with other screens: wall 9:20 AM (ADM-03), Northwind run 9:24 AM, Season Progress Reporter 2 m 41 s (WB-08), envelope E13, Harborview "Synced Sep 11".
- ADM-07 acceptance: the default view shows "Policy principal: 0 events" because ADM-04 has it off.
- ADM-07 acceptance: no edit or delete affordance anywhere; the export carries a signed manifest.

## Figures

- 18,406 events; 1,962 via Agent; 14 rows shown in a.
- Copperleaf 2026-08: 11,860.00 + 700.00 + 2,140.00 + 5,320.00 = 20,020.00; not included 14,900.00 (> $10,000 other accruals) → Priya Raman.
- IPs only in 198.51.100.0/24 and 203.0.113.0/24.

## AVOID

Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, the actor "Accrued Agent" on any approval, acceptance or sign-off row; edit or delete controls on events; "Approved by Accrual Agent"; out-of-order same-minute events (seconds in the drawer).

## Deviations

| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-1 | c is rendered for **Margaret Okonkwo**; Felix's variant shows values withheld | DEC-60: values resolved at read time for readers in scope | DEC-60, DEC-411 |
| DV-2 | Request-context fields (IP, device, session) are null for readers other than firm admin, security admin and quality partner | DEC-420 | DEC-420 |
| DV-3 | d is fixture-only | DEC-53 / ADR P-08: no policy actor writes before GA | DEC-53, DEC-411 |
| DV-4 | Rows whose producers are not built on staging by S12 render from fixtures only (engagement run, Workbench, inbox email, envelope, tax return) | G-02 §5.4 | DEC-411 |

## Parity

| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| a, b, f | C (locked) | 2.92 / 1.61 / 0.73 | locked 2026-10-29 (G-02-T26), measured on `parity-screens`; mask IP columns on staging, the content-hash text and times |
| c, e, g | C report-only | 8.77 / 11.64 / 3.67 | G-02-T21 recorded these as locked on 2026-10-27 before any baseline existed; measured 2026-10-29 (G-02-T26) over 3 %: c persona (DV-1) until the board is revised; open gap |
| d | C report-only | 3.04 | fixture mode only |

## Open gaps

- The design-tool frames for the values-withheld state and the design-fidelity sign-off are made on the Wave 3 canvas outside the repository.
