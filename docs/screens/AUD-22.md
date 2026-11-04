# AUD-22 · Governance communications (AU-C 260 planning letter; AU-C 260 / 265 / 703 completion letters)

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/governance` · `?tab=` and `?dock=` in the URL; sheets and dialogs in local state |
| Template and host frame | T10 DocumentOnWell (structure 470 = communications list, recipients, built-from; paper 896) · `Wave 2 - Audit Completion.dc.html` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-22 Governance communications -AU-C 260 planning letter AU-C 260 265/` (README.md, spec.md; revision.md wins where present) |
| Epic and tasks | A-07 · stubs T05 · migration T08 · templates T12 · service T26 · screen T29 · clocks T36 · SPEC-644 |
| Manifest status | planned (fixture with its screen task; live with A-07-T47) |

## States
Clock is the demo clock (DEC-27): CDT (UTC−5) until Sun Nov 1, 2026, CST (UTC−6) after. Snapshots
E0–E7 are the Northwind PY2025 completion timeline of A-07-T11's scenario.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | margaret-okonkwo | Thu Sep 17, 2026, 2:30 PM CDT | planning | Planning letter awaiting approval | live (T26) |
| a2 | margaret-okonkwo | 2:30 PM CDT | interact | Approve & send… O3: recipients, channel, delivery to the governance room; step-up | live (T26) |
| a3 | hannah-leclerc | 2:30 PM CDT | planning | Manager view: Request approval… | live (T26) |
| b | margaret-okonkwo | Mon Sep 21, 2026 CDT | planning | Sent · acknowledged: "Acknowledged Sep 21 · Benefits Committee"; watermark removed, paper locked | live (T26) |
| c | margaret-okonkwo | Fri Oct 9, 2026 CDT | E3 | Completion: AU-C 265/703 draft; "Due Dec 8, 2026 · 60 days after release" | live (T26, T36) |
| d | margaret-okonkwo | Tue Nov 24, 2026 CST | post-release | Acknowledged Nov 24 (sent Nov 20) | live (T26) |
| e | margaret-okonkwo | Wed Dec 9, 2026 CST | illustrative | Overdue: red-tint "Overdue · AU-C 265" | live (T36) |
| loading, not allowed, off | as AUD-02 | — | — | flag off (from A-07-T33): 404 and the C-20 state; 501 before | live |

Parity tier: Tier C on the locked artboards named in A-07-T48; Tier D on the T2/T10 geometry.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET …/governance-communications[/{id}]` | `GovernanceListOut` · `GovernanceCommunicationOut` | `governance_comm.read` | — |
| write | `POST …` `{kind}` · `POST …/{id}/compose` (202) · `PATCH …/sections/{key}` | regenerate keeps human edits | `governance_comm.draft` | manager, senior |
| write | `POST …/{id}/request-approval` · `POST …/{id}/approve-and-send` (step-up, Idempotency-Key) | `GovernanceSendIn` | `governance_comm.request_approval` · `governance_comm.approve_send` | EP sends; human only |
| read · write | `GET`/`PUT …/governance-recipients` | `GovernanceRecipientsOut` | `governance_comm.read` · `governance_comm.manage_recipients` | EP, manager |

Every endpoint is in `docs/contracts/audit-completion.md` (A-07-T04, T05); 501 until its task.

## Status
`governance_communication`.

## Copy
"Approve & send…", "Request approval…", "Acknowledged Sep 21 · Benefits Committee", "Due Dec 8, 2026 · 60 days after release", "Overdue · AU-C 265", "Regenerate". Copy keys live in `apps/web/src/copy/aud-22.ts` with the screen task; the words are the handoff's.

## Deviations
- DV-6: "2 of 3 required sent" (required set per engagement type; DF-27)
- POR-15 delivery through R-02; where POR-15 is off, a SIG-02 acknowledgement envelope (DEC-83)

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 | AUD-01 | handoff link (A-01; status in the manifest) |
| Opens AUD-02 | AUD-02 | handoff link (A-01; status in the manifest) |
| Opens AUD-08 | AUD-08 | handoff link (A-04; status in the manifest) |
| Opens AUD-09 | AUD-09 | handoff link (A-04; status in the manifest) |
| Opens AUD-10 | AUD-10 | handoff link (A-04; status in the manifest) |
| Opens AUD-15 | AUD-15 | handoff link (A-06; status in the manifest) |
| Opens CLI-04 | CLI-04 | handoff link (P-07; status in the manifest) |
| Opens ENG-02 | ENG-02 | handoff link (P-07; status in the manifest) |
| Opens KNW-03 | KNW-03 | handoff link (K-01; status in the manifest) |
| Opens POR-15 | POR-15 | handoff link (R-02; status in the manifest) |

## Acceptance
- Every artboard letter above carries live, fixture-only or deferred with its owning task or epic.
- No agent-owned control carries Approve, Sign off, Release, Send, Post or Decide; final verbs are never optimistic (A-07-T44).
