# ADM-05 · Consent registry (§7216)

| Field | Value |
|---|---|
| Route and params | `/settings/consents`; `?status=expiring`, `?purpose=`, `?client=`; drawer `?ov=consent:<consentSetId>` (O2 480) |
| Template and host frame | T1 `IndexList` with `StatusTileRow` inside T12 `SettingsLayout` · `Wave 3 - Admin & Governance.dc.html#adm05` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ADM-05 Consent registry --7216-/` (README.md, spec.md) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | T-01 · contract T-01-T05; fixtures T09; build T13, T14 |
| Spec and ADRs | SPEC-501 AC-11; ADR-231; R-04 |
| Flags | `consents.registry` |
| Manifest status | `fixture` since T-01-T13 (a, b, f, g built; c, d, e, h with T-01-T22); `live` with the C19 routes (pilot posture: agents off) |

## States
| Artboard | Viewer | Clock (CT) | Data condition | Parity tier | Status |
|---|---|---|---|---|---|
| a | grace-holloway | Mon Sep 14, 2026 9:24 AM | Default: 218 consents (212 + 2 + 1 + 1 + 1 + 1), AI-use 214 (211 + 3), 14 visible rows | C | fixture (T-01-T09) |
| b | grace-holloway | 9:24 AM | Expiring filter | C | fixture (T-01-T09) |
| c | grace-holloway | 9:24 AM | Evidence drawer · Feld | C | fixture (T-01-T09) |
| d | grace-holloway | 9:24 AM | Renew 3… (Iyer, Rao, Osterberg) | C | fixture (T-01-T09) |
| e | harold-stein | 9:24 AM | Declined · Harold Stein | C | fixture (T-01-T09) |
| f | grace-holloway | 9:24 AM | No matches (filtered empty) | C | fixture (T-01-T09) |
| g | grace-holloway | 9:24 AM | 3 selected (selection bar) | C | fixture (T-01-T09) |
| h | grace-holloway | 9:24 AM | Renewals drafted (toast) | C | fixture (T-01-T09) |

Non-artboard: not allowed (a principal the matrix refuses: 404, no count), flag off (the frame with the C-20 "not turned on" state), loading and error (F-05 ViewStates), walled rows absent with no hidden count.

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/consents?status=&purpose=&tax_year=&offshore=` | ListPage[ConsentOut] | `consent.read` |
| read | `GET /v1/consents/summary` | ConsentSummaryOut | `consent.read` |
| read | `GET /v1/consents/{id}; …/documents/{doc}/evidence` | ConsentDetailOut | consent.read, consent.evidence_download |
| write | `POST /v1/consents/renewals` | ConsentDraftsOut | `consent.request` |
| write | `POST /v1/consents/records, /{id}/declines, /{id}/revocations` | ConsentOut | consent.record (fresh MFA) |
| write | `POST /v1/consents/exports` | ConsentExportOut (202) | consent.export (fresh MFA) |

Every write denies the agent and the system; no agent-owned control says Approve, Release, Send, Post or Decide.

## Status
`consent` (blueprint §3.3.1 words, plus `superseded`).

## Copy
Verbatim from the handoff's spec.md into `screens/ADM-05/copy.ts`. Banned (T-01 §5.7; `apps/web/src/copy-bans.test.ts`): any phrase in which Accrued or the agent transmits, e-files or files a return; vendor logos.

## Links
Outbound: CLI-05 d (per taxpayer), SIG-01 (envelopes), ADM-04 D (counts). Inbound: Settings nav, ADM-04.
| Opens ADM-01 · Settings home | ADM-01 | planned (handoff link; tooltip-only) |
| Opens KNW-05 · Templates filtered to consents | KNW-05 | planned (handoff link; tooltip-only) |
| Opens CLI-05 · Consents | CLI-05 | planned (handoff link; tooltip-only) |
| Opens ADM-02 · People | ADM-02 | planned (handoff link; tooltip-only) |
| Opens ADM-03 · Offices & teams | ADM-03 | planned (handoff link; tooltip-only) |
| Opens ADM-06 · Security | ADM-06 | planned (handoff link; tooltip-only) |
| Opens ADM-04 · AI policy | ADM-04 | planned (handoff link; tooltip-only) |
| Opens ADM-09 · Developer | ADM-09 | planned (handoff link; tooltip-only) |
| Opens ADM-08 · Integrations | ADM-08 | planned (handoff link; tooltip-only) |
| Opens ADM-10 · Portal | ADM-10 | planned (handoff link; tooltip-only) |
| Opens ADM-11 · Quality | ADM-11 | planned (handoff link; tooltip-only) |
| Opens ADM-12 · Monitoring | ADM-12 | planned (handoff link; tooltip-only) |
| Opens ADM-07 · Audit log | ADM-07 | planned (handoff link; tooltip-only) |
| Opens SIG-02 with a purpose picker | SIG-02 | planned (handoff link; tooltip-only) |
| Opens SIG-01 · envelope E17 | SIG-01 | planned (handoff link; tooltip-only) |

## Acceptance
- ADM-05 acceptance: every artboard a, b, c, d, e, f, g, h renders from its fixture scenario with the persona and clock above.
- ADM-05 acceptance: the figures in the States table foot in the seed test (T-01-T09).
- ADM-05 acceptance: status is never colour alone; every pill and disc has text (T-01 §5.6).

## AVOID
Gradients, emoji, blue, heavy shadows, invented colours or data, boxed inputs, the agent as approver or transmitter, an Accrued mark on anything the client sees.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| D1 | DF-16: recipients come from the register, never free text | DF-16 | T-01 §2.1 |
| D2 | Walled clients' rows are absent with no hidden count | DEC-43 | T-01 §3.5 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c, d, e, f, g, h | C | — | measured with the screen build |
| host | D | — | tiles 120 × 72, note card 352 × 72, rows 44 h, selection bar 44 h, drawer 480 |

## Open gaps
- Status objects live in the registry since T-01-T06; the contracts move from `Literal` types to the registry's enums when the routes go live.
- T-01-T13 (DEC-1262): ConsentOut gains `declined_at`, `revoked_at` and `signers` (with `title`), additively, for the Signed column and the signer line; Request consent… and Renew 3… stay disabled with their planned tooltips until SIG-02 (part 2).

