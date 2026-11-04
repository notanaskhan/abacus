# AUD-24 · Issuance & release

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/release` · `?tab=` and `?dock=` in the URL; sheets and dialogs in local state |
| Template and host frame | T2 with dock "Deliverables" (rail 330 · canvas 696 gate cards · dock 330) · `Wave 2 - Audit Completion.dc.html` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-24 Issuance and release/` (README.md, spec.md; revision.md wins where present) |
| Epic and tasks | A-07 · stubs T05 · migration T08 · gates T15 · release T30 · filings and clocks T36 · screen T38 · SPEC-644 |
| Manifest status | planned (fixture with its screen task; live with A-07-T47) |

## States
Clock is the demo clock (DEC-27): CDT (UTC−5) until Sun Nov 1, 2026, CST (UTC−6) after. Snapshots
E0–E7 are the Northwind PY2025 completion timeline of A-07-T11's scenario.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | margaret-okonkwo | Fri Oct 9, 2026, 10:05 AM CDT | E3 | Ready to release: G5, G6, G7 met; also-required all ✓ (FS approved Oct 8, bring-down #4240 9:04 AM, independence 5 of 5, final materiality v3, AU-C 260 completion letter sent Oct 8) | live (T30) |
| b | margaret-okonkwo | Tue Oct 6, 2026 CDT | E2 replay | Blocked: G7 "Not met · Out for signature since Oct 6"; "Blocked by G7 · representation letter" | live (T30) |
| c | margaret-okonkwo | 10:06 AM CDT | interact | Release dialog (O3 500): summary, the EP attestation checkbox, step-up | live (T30) |
| d | margaret-okonkwo | 10:07 AM CDT | E4 | Released · G8: clock row "Archive in 60 days · by Dec 8, 2026"; toast | live (T30) |
| e | hannah-leclerc | 10:05 AM CDT | E3 | Non-partner viewer: "Only Margaret Okonkwo can release this report" | live (T30) |
| f | hannah-leclerc | Wed Oct 14, 2026 CDT | E4 | Filed: "Filed Oct 14, 2026 · EFAST2 acknowledgment received" | live (T36) |
| loading, not allowed, off | as AUD-02 | — | — | flag off (from A-07-T33): 404 and the C-20 state; 501 before | live |

Parity tier: Tier C on the locked artboards named in A-07-T48; Tier D on the T2/T10 geometry.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET …/release` | `AuditReleaseOut` (gates, also-required, `gate_hash`, `viewer_can_release`) | `report.read` | — |
| write | `POST …/release` (202, Idempotency-Key, step-up) | `ReleaseIn` | `report.release` | EP only; 409 `gates_not_met`; no hold, no Undo (DEC-2260) |
| read · write | `GET …/filings` · `PATCH …/filings/{id}` | `FilingOut` | `report.read` · `filing.update` | manager, senior |

Every endpoint is in `docs/contracts/audit-completion.md` (A-07-T04, T05); 501 until its task.

## Status
`report_release`, `filing`, `audit_engagement`.

## Copy
"I am the engagement partner and I authorize release of this report", "Released Oct 9, 2026 · 10:07 AM · Margaret Okonkwo", "Archive in 60 days · by Dec 8, 2026", "Report released · delivered to Dana Kowalski", "Only Margaret Okonkwo can release this report", "Blocked by G7 · representation letter", "Filed Oct 14, 2026 · EFAST2 acknowledgment received", "Releasing…". Copy keys live in `apps/web/src/copy/aud-24.ts` with the screen task; the words are the handoff's.

## Deviations
- DV-6: "2 of 3 required sent"
- DV-7: transient "Releasing…" button spinner (≤ 3 s)

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 | AUD-01 | handoff link (A-01; status in the manifest) |
| Opens AUD-03 | AUD-03 | handoff link (A-01; status in the manifest) |
| Opens AUD-25 | AUD-25 | handoff link (A-07; status in the manifest) |
| Opens SHL-08 | SHL-08 | handoff link (P-04; status in the manifest) |

## Acceptance
- Every artboard letter above carries live, fixture-only or deferred with its owning task or epic.
- No agent-owned control carries Approve, Sign off, Release, Send, Post or Decide; final verbs are never optimistic (A-07-T44).
