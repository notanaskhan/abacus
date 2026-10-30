# CLI-05 · Tax profile · authorizations and consents · Transcripts

| Field | Value |
|---|---|
| Route and params | `/clients/$clientId/tax-profile/:sub` (`sub` ∈ elections, authorizations, consents, transcripts); `?transcript=<id>` selects a register row |
| Template and host frame | T2 `RecordCockpit` (client record tab slot, P-07-T19) · `Wave 3 - Home & Clients.dc.html#cli05` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLI-05 Tax profile- authorizations and consents - with Transcripts/` (README.md, spec.md) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | T-01 · contract T-01-T05 (this file); fixtures T09; build T43–T46 |
| Spec and ADRs | SPEC-501 AC-11; ADR-231; R-04 |
| Flags | `clients.tax_profile`; consents from `consents.registry` |
| Manifest status | `fixture` since T-01-T14 (d, f: the consents section; a, b, c, e, g with T-01-T43 to T46); `live` with C19's routes (pilot posture: agents off) |

## States
| Artboard | Viewer | Clock (CT) | Data condition | Parity tier | Status |
|---|---|---|---|---|---|
| a | kevin-osei | Mon Sep 14, 2026 9:24 AM | Transcripts · 2 differences: Whitley TY2024 and TY2025 W&I and Account against the returns as filed; 1,870.00 + 1,250.00 = 3,120.00, 686.40 + 66.61 = 753.01 | C | fixture (T-01-T09) |
| b | kevin-osei | Mon Sep 14, 2026 9:04 AM | Transcripts · none yet: Whitley before upload | C | fixture (T-01-T09) |
| c | kevin-osei | 9:24 AM | Authorizations: 8821 for 2022–2026 on file | C | fixture (T-01-T09) |
| d | kevin-osei | 9:24 AM | Consents: Whitley use and AI disclosure signed Jan 20, 2026, with agent reads | C | fixture (T-01-T09) |
| e | kevin-osei | 9:24 AM | Elections · Ridgeline (PTET 28,044, 17,070, 18,982) | C | fixture (T-01-T09) |
| f | kevin-osei | 9:24 AM | Consent partially signed · Ferris envelope E17 (Morgan ✓ Sep 9, Kai ○) | C | fixture (T-01-T09) |
| g | kevin-osei | 9:24 AM | No authorization · Santos | C | fixture (T-01-T09) |

Non-artboard: not allowed (a principal the matrix refuses: 404, no count), flag off (the frame with the C-20 "not turned on" state), loading and error (F-05 ViewStates), walled rows absent with no hidden count.

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/client-entities/{id}/tax-profile` | TaxProfileOut | `tax_profile.read` |
| read | `GET /v1/client-entities/{id}/consents` | list[ConsentOut] | `consent.read` |
| write | `PUT /v1/client-entities/{id}/elections/{kind}` | TaxElectionIn | `tax_election.manage` |
| read/write | `GET/POST /v1/client-entities/{id}/authorizations; POST …/requests` | TaxAuthorizationOut | `tax_authorization.manage` |
| write | `POST /v1/client-entities/{id}/transcripts; POST /v1/transcripts/{id}/comparisons` | TranscriptOut, TranscriptComparisonOut | transcript.upload, transcript.compare |

Every write denies the agent and the system; no agent-owned control says Approve, Release, Send, Post or Decide.

## Status
`consent`, `tax_authorization` (`not_on_file` derived).

## Copy
Verbatim from the handoff's spec.md into `screens/CLI-05/copy.ts`. Banned (T-01 §5.7; `apps/web/src/copy-bans.test.ts`): any phrase in which Accrued or the agent transmits, e-files or files a return; vendor logos.

## Links
Outbound: SHL-08 (difference cells, E5), SIG-01/SIG-02 (consent envelope), NOT-02 (planned), TAX-02 (return). Inbound: CLI-02 Tax profile tab.
| Open in the viewer (SHL-08) | SHL-08 | planned (handoff link; tooltip-only) |
| Opens NOT-02 · CP2000 · TY2024 · Marcus & Dana Whitley | NOT-02 | planned (handoff link; tooltip-only) |
| Form 8821 for 2022–2026 lets the firm receive transcripts and notices, not represent; Draft Form 2848… opens SIG-02 | SIG-02 | planned (handoff link; tooltip-only) |

## Acceptance
- CLI-05 acceptance: every artboard a, b, c, d, e, f, g renders from its fixture scenario with the persona and clock above.
- CLI-05 acceptance: the figures in the States table foot in the seed test (T-01-T09).
- CLI-05 acceptance: status is never colour alone; every pill and disc has text (T-01 §5.6).

## AVOID
Gradients, emoji, blue, heavy shadows, invented colours or data, boxed inputs, the agent as approver or transmitter, an Accrued mark on anything the client sees.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| D1 | The identity band shows the TIN's last four with Reveal (logged) through P-03's MaskedValue | DEC-52 | DEC-1160 |
| D2 | CLI-05 a agent blocks are fixture-only until the gate (T-01-T12) is live | condition 6 | T-01 §2.2 |
| D3 | DF-11: consents use the email-code identity method | DF-11 | T-01 §2.1 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c, d, e, f, g | C | — | measured with the screen build |
| host | D | — | rail rows 52 h, register rows 40 h, detail rows 36 h |

## Open gaps
- Status objects live in the registry since T-01-T06; the contracts move from `Literal` types to the registry's enums when the routes go live.
- T-01-T14 (DEC-1263): TaxProfileOut gains the subbar facts (`client_name`, `client_kind`, `partner_name`, `office_name`), the Identity band (`identity`, `portal_user_name`, `resident_state`) and ConsentOut `template_name`, additively. The route takes `?entity=`; without it the record's first entity opens. The partially signed banner keeps the handoff's words (DF-04's agents-off words arrive with the copy registry). Resend…, Request consent… and the Open notices row are planned links (tooltip-only).

