# TAX-12 · Return · Delivery and e-file · Feld 2025 Form 1040

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/delivery?step=<row>` (`step` ∈ final-approval, exported, diagnostics, packet, authorizations, payments, transmission, acks, delivery) inside `ReturnFrame` |
| Template and host frame | T2 `RecordCockpit` · `Wave 2 - Tax Returns.dc.html#tax12` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-12 Return - Delivery and e-file - Feld 2025 Form 1040/` (README.md, spec.md) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | T-01 · contract T-01-T05; fixtures T09; build T35–T40 |
| Spec and ADRs | SPEC-501 AC-11; ADR-231; R-04 |
| Flags | `tax.delivery_efile` |
| Manifest status | planned; built on fixtures with T-01-T09's scenarios, `live` with its build tasks (pilot posture: agents off) |

## States
| Artboard | Viewer | Clock (CT) | Data condition | Parity tier | Status |
|---|---|---|---|---|---|
| a | grace-holloway | Thu Sep 17, 2026 9:30 AM | Awaiting signature: envelope sent Sep 16 1:05 PM, Claire signed 7:48 PM, Jonah viewed 8:02 AM | C (lock) | fixture (T-01-T09) |
| a2 | grace-holloway | Thu Sep 17, 2026 9:30 AM | Send reminder… | C (lock) | fixture (T-01-T09) |
| b | grace-holloway | Mon Sep 14, 2026 9:24 AM | Blocked: In review · Manager | C (lock) | fixture (T-01-T09) |
| c | grace-holloway | Thu Sep 17, 2026 6:12 PM | Ready to transmit: completed; ERO Daniel Reyes | C (lock) | fixture (T-01-T09) |
| c2 | daniel-reyes | Fri Sep 18, 2026 11:06 AM | Mark transmitted (the ERO's record) | C (lock) | fixture (T-01-T09) |
| d | grace-holloway | Sat Sep 19, 2026 9:12 AM | Accepted: four acks; refund 123,476 − 123,223 = 253; NY 52,805 − 51,536 = 1,269 | C (lock) | fixture (T-01-T09) |
| e | grace-holloway | Thu Sep 17, 2026 9:30 AM | Rejected: IND-181-01 | C (lock) | fixture (T-01-T09) |

Non-artboard: not allowed (a principal the matrix refuses: 404, no count), flag off (the frame with the C-20 "not turned on" state), loading and error (F-05 ViewStates), walled rows absent with no hidden count.

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/tax-returns/{id}/delivery` | DeliveryOut | `tax_return.read` |
| write | `POST …/delivery-packet:assemble; PATCH /v1/delivery-packets/{id}; POST …/letter:regenerate` | DeliveryPacketOut | `delivery_packet.prepare` |
| write | `POST /v1/delivery-packets/{id}/approve` | DeliveryPacketOut | `delivery_packet.approve` |
| write | `POST /v1/tax-returns/{id}/efile-envelope, …/ero-notices` | EfileEnvelopeOut, EroNoticeOut | `delivery_packet.prepare` |
| write | `POST /v1/tax-returns/{id}/transmissions` | TransmissionIn → TransmissionOut | `transmission.record` |
| write | `POST /v1/tax-returns/{id}/acks` | EfileAckIn → EfileAckOut | `efile_ack.record` |
| write | `POST /v1/tax-returns/{id}/deliverables:publish` | DeliverablePublishOut | `deliverable.publish` |

Every write denies the agent and the system; no agent-owned control says Approve, Release, Send, Post or Decide.

## Status
`efile_ack`, `envelope`, `envelope_signer` (N-02), `consent`.

## Copy
Verbatim from the handoff's spec.md into `screens/TAX-12/copy.ts`. Banned (T-01 §5.7; `apps/web/src/copy-bans.test.ts`): any phrase in which Accrued or the agent transmits, e-files or files a return; vendor logos.

## Links
Outbound: SIG-01/SIG-02 (8879 envelope), SHL-12 h, TAX-13 (planned), POR-02 (client copy). Inbound: TAX-02 Delivery tab.

## Acceptance
- TAX-12 acceptance: every artboard a, a2, b, c, c2, d, e renders from its fixture scenario with the persona and clock above.
- TAX-12 acceptance: the figures in the States table foot in the seed test (T-01-T09).
- TAX-12 acceptance: status is never colour alone; every pill and disc has text (T-01 §5.6).

## AVOID
Gradients, emoji, blue, heavy shadows, invented colours or data, boxed inputs, the agent as approver or transmitter, an Accrued mark on anything the client sees.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| D1 | Accrued records the transmission; the ERO transmits in the engine (R-04): "Mark transmitted" is a person's record | R-04 | DEC-1158 |
| D2 | DF-21 and DEC-38: the packet is approved by the signer or a manager-level person | DEC-38 | DEC-1156 |
| D3 | The cover letter comes from a template (ADR P-25 off); TAX-12 e agent blocks are fixture-only | ADR P-25 | T-01 §2.2 |
| D4 | DF-07: the Signatures & files segment | DF-07 | T-01 §2.1 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, a2, b, c, c2, d, e | C (lock) | — | measured with the screen build |
| host | D | — | rail 330, PhaseRow 44 h, OverviewCard tile 34, canvas 612 + 388, signer rows 52 h, KV rows 33 h, gate button 36 h |

## Open gaps
- Status objects live in the registry since T-01-T06; the contracts move from `Literal` types to the registry's enums when the routes go live.
