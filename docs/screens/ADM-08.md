# ADM-08 · Integration settings

| Field | Value |
|---|---|
| Route and params | `/settings/integrations`; `?segment=tax-engine|ledgers|mailboxes`; drawer `?ov=integration-mapping:users` (O2) |
| Template and host frame | T12 `SettingsLayout` · `Wave 3 - Admin & Governance.dc.html#adm08` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ADM-08 Integration settings/` (README.md, spec.md) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | T-01 · contract T-01-T05; fixtures T09; build T20, T21 |
| Spec and ADRs | SPEC-501 AC-11; ADR-231; R-04 |
| Flags | `tax.engine_bridge` |
| Manifest status | planned; built on fixtures with T-01-T09's scenarios, `live` with its build tasks (pilot posture: agents off) |

## States
| Artboard | Viewer | Clock (CT) | Data condition | Parity tier | Status |
|---|---|---|---|---|---|
| a | felix-andersen | Mon Sep 14, 2026 9:24 AM | Tax engine: CCH file bridge, 21 users, CHI/DEN/NYC, status mirror | C | fixture (T-01-T09) |
| b | felix-andersen | 9:24 AM | Ledgers: 9 connected (fixture), Bluestem Needs reauth | C | fixture (T-01-T09) |
| c | felix-andersen | 9:24 AM | Mailboxes | C | fixture (T-01-T09) |
| d | felix-andersen | 9:24 AM | Test passed | C | fixture (T-01-T09) |
| e | felix-andersen | 9:24 AM | Sage Intacct test failed | C | fixture (T-01-T09) |
| f | felix-andersen | 9:24 AM | Mapping conflict (409 `mapping_conflict`) | C | fixture (T-01-T09) |
| g | felix-andersen | 9:24 AM | Edit mapping (drawer) | C | fixture (T-01-T09) |

Non-artboard: not allowed (a principal the matrix refuses: 404, no count), flag off (the frame with the C-20 "not turned on" state), loading and error (F-05 ViewStates), walled rows absent with no hidden count.

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/firm/integrations/{key}/settings` | EngineSettingsOut | `integration.read` |
| write | `PUT …/settings, …/user-mapping, …/office-mapping, …/status-mirror` | EngineSettingsIn, MappingIn | integration.configure (fresh MFA) |
| write | `POST …/test` | FormatCheckOut | `integration.test` |

Every write denies the agent and the system; no agent-owned control says Approve, Release, Send, Post or Decide.

## Status
`return_sync_chip` words where the tax engine card shows them.

## Copy
Verbatim from the handoff's spec.md into `screens/ADM-08/copy.ts`. Banned (T-01 §5.7; `apps/web/src/copy-bans.test.ts`): any phrase in which Accrued or the agent transmits, e-files or files a return; vendor logos.

## Links
Outbound: ADM-01 (settings), TAX-09 (engine sync). Inbound: Settings nav.
| Opens ADM-01 · Settings home | ADM-01 | planned (handoff link; tooltip-only) |
| Opens POR-20 · Reconnect request (Published · v1) | POR-20 | planned (handoff link; tooltip-only) |
| Opens WB-10 · Connect | WB-10 | planned (handoff link; tooltip-only) |
| Opens ADM-02 · People | ADM-02 | planned (handoff link; tooltip-only) |
| Opens ADM-03 · Offices & teams | ADM-03 | planned (handoff link; tooltip-only) |
| Opens ADM-06 · Security | ADM-06 | planned (handoff link; tooltip-only) |
| Opens ADM-04 · AI policy | ADM-04 | planned (handoff link; tooltip-only) |
| Opens ADM-05 · Consents | ADM-05 | planned (handoff link; tooltip-only) |
| Opens ADM-09 · Developer | ADM-09 | planned (handoff link; tooltip-only) |
| Opens ADM-10 · Portal | ADM-10 | planned (handoff link; tooltip-only) |
| Opens ADM-11 · Quality | ADM-11 | planned (handoff link; tooltip-only) |
| Opens ADM-12 · Monitoring | ADM-12 | planned (handoff link; tooltip-only) |
| Opens ADM-07 · Audit log | ADM-07 | planned (handoff link; tooltip-only) |
| Opens TAX-09 · Tax engine sync · Jonah & Claire Feld · 2025 Form 1040 | TAX-09 | planned (handoff link; tooltip-only) |
| Opens WB-11 · CCH Axcess Tax | WB-11 | planned (handoff link; tooltip-only) |
| Opens INB-01 · Inbox filtered to unmatched senders | INB-01 | planned (handoff link; tooltip-only) |

## Acceptance
- ADM-08 acceptance: every artboard a, b, c, d, e, f, g renders from its fixture scenario with the persona and clock above.
- ADM-08 acceptance: the figures in the States table foot in the seed test (T-01-T09).
- ADM-08 acceptance: status is never colour alone; every pill and disc has text (T-01 §5.6).

## AVOID
Gradients, emoji, blue, heavy shadows, invented colours or data, boxed inputs, the agent as approver or transmitter, an Accrued mark on anything the client sees.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| D1 | File-bridge mode only: no API credentials field; W2 is a file the firm carries | ADR-231, P-18 | DEC-1158 |
| D2 | Ledger and mailbox segments render A-02's and N-01's fixture rows until their epics wire them | fixture | T-01 §2.2 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c, d, e, f, g | C | — | measured with the screen build |
| host | D | — | fieldsets 860, Connected card 230, ValueRow 34 h, sub-headers on `--nested` |

## Open gaps
- Status objects live in the registry since T-01-T06; the contracts move from `Literal` types to the registry's enums when the routes go live.
