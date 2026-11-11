# AUD-18 · EQR workspace

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/eqr` · `?tab=` and `?dock=` in the URL; sheets and dialogs in local state |
| Template and host frame | T2 RecordCockpit with dock (rail 330 EQR checklist · canvas 696 judgments digest · dock 330 Notes · Agent) · `Wave 2 - Audit Completion.dc.html` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-18 EQR workspace/` (README.md, spec.md; revision.md wins where present) |
| Epic and tasks | A-07 · stubs T04 · migration T07 · fixtures T11 · screen T17 · service T18 · gate G6 T15 · agent T32 · parity T48 · SPEC-644 |
| Manifest status | fixture (final, A-07-T53, S36) |

## States
Clock is the demo clock (DEC-27): CDT (UTC−5) until Sun Nov 1, 2026, CST (UTC−6) after. Snapshots
E0–E7 are the Northwind PY2025 completion timeline of A-07-T11's scenario.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | thomas-whitcombe | Mon Oct 5, 2026, 11:05 AM CDT | E1 | 6 of 10 items done; EQR-1 Responded, EQR-2 Open with Hannah Leclerc; six digest cards (materiality 252,200 / 189,150 / 12,610; significant risks; deficiency severity; SUM 34,150 = 18.1% of PM; service-organisation reliance; opinion form); Concur… disabled with the blocker sentence | live (T18) |
| b | thomas-whitcombe | Mon Oct 5, 2026, 4:40 PM CDT | E1 | 10 of 10, both notes cleared; Concur… primary | live (T18) |
| b2 | thomas-whitcombe | 4:40 PM CDT | interact | Concur… O3 sheet: six judgments, date "October 5, 2026", the not-involved checkbox, step-up | live (T18) |
| c | thomas-whitcombe | 4:41 PM CDT | E1 | Concurrence recorded: green-tint card "Concurred · Oct 5, 2026 · 4:40 PM · Thomas Whitcombe"; audit bar stays "In review"; G6 met | live (T18, T15) |
| d | thomas-whitcombe | 11:05 AM CDT | `?dock=agent` | Agent tab: ToolCard "Assemble judgments digest"; narration "I have not evaluated them." | live (T32) |
| e | hannah-leclerc | 11:05 AM CDT | E1 | Not the EQR: read-only, "Only the assigned EQR can concur."; can Respond… to EQR-2 | live (T18) |
| loading, not allowed, off | as AUD-02 | — | — | flag off (from A-07-T33): 404 and the C-20 state; 501 before | live |

Parity tier: Tier C on the locked artboards named in A-07-T48; Tier D on the T2/T10 geometry.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET …/eqr` | `EqrReviewOut` | `eqr.read` | team, EQR; `viewer_is_eqr` drives e |
| write | `POST …/eqr/digest:build` (202) | `CompletionRunAcceptedOut` | `eqr.build_digest` | EP, manager, EQR; code only |
| write | `POST …/eqr/digest/{card_id}/reviewed` | `EqrCardReviewIn` → `EqrDigestCardOut` | `eqr.mark_reviewed` | assigned EQR only (`function_in: eqr`) |
| write | `PATCH …/eqr/checklist/{item_key}` | `EqrChecklistIn` | `eqr.checklist_update` | assigned EQR only |
| write | `POST …/eqr/concur` | `EqrConcurIn` (step-up) | `eqr.concur` | assigned EQR; 403 `eqr_only`; 409 `checklist_incomplete` |
| write | C3 review notes `{kind: eqr}` | P-04 | `review_note.*` | EQR raises and clears; EP or manager responds |

Every endpoint is in `docs/contracts/audit-completion.md` (A-07-T04, T05); 501 until its task.

## Status
`eqr_review`, `eqr_checklist_item`, `review_note`.

## Copy
"Concur…", "Blocked: 4 checklist items open · 2 EQR notes not cleared.", "I was not involved in performing this engagement", "Concurred · Oct 5, 2026 · 4:40 PM · Thomas Whitcombe", "I built the digest from 6 decision cards and 3 conclusions. I have not evaluated them.", "Only the assigned EQR can concur.", "L5 sign off…" (DF-26), "Mark reviewed". Copy keys live in `apps/web/src/copy/aud-18.ts` with the screen task; the words are the handoff's.

## Deviations
- DV-3: "L5 sign off…" in the ··· menu of EQR-required workpaper rows opens SHL-12 g (DF-26)
- DV-8: the C-03 consultation chip opens A-06's minimal consultation record until AUD-28 (Q-05)

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 | AUD-01 | handoff link (A-01; status in the manifest) |
| Opens AUD-02 | AUD-02 | handoff link (A-01; status in the manifest) |
| Opens AUD-03 | AUD-03 | handoff link (A-01; status in the manifest) |
| Opens AUD-07 | AUD-07 | handoff link (A-04; status in the manifest) |
| Opens AUD-08 | AUD-08 | handoff link (A-04; status in the manifest) |
| Opens AUD-10 | AUD-10 | handoff link (A-04; status in the manifest) |
| Opens AUD-15 | AUD-15 | handoff link (A-06; status in the manifest) |
| Opens AUD-16 | AUD-16 | handoff link (A-06; status in the manifest) |
| Opens AUD-20 | AUD-20 | handoff link (A-06; status in the manifest) |
| Opens AUD-22 | AUD-22 | handoff link (A-07; status in the manifest) |
| Opens AUD-23 | AUD-23 | handoff link (A-07; status in the manifest) |
| Opens AUD-28 | AUD-28 | planned link (DV-8; inline list, chip or download until Q-05) |
| Opens WB-09 | WB-09 | handoff link (P-09; status in the manifest) |

## Acceptance
- Every artboard letter above carries live, fixture-only or deferred with its owning task or epic.
- No agent-owned control carries Approve, Sign off, Release, Send, Post or Decide; final verbs are never optimistic (A-07-T44).

## Final status (A-07-T53, S36)

Built on fixtures (A-07-T17); A-07-T18's EQR service is live but the screen has no live host yet, so every artboard is **fixture-only** until the AUD-18 live wiring (flagged S36, A-07-T53).

| Artboard | Final status |
|---|---|
| a | built · fixture-only |
| b | built · fixture-only |
| b2 | built · fixture-only |
| c | built · fixture-only |
| d | built · fixture-only |
| e | built · fixture-only |

| Deviation | Evidence |
|---|---|
| DV-3 | **Not found in code:** `screens/AUD-18` draws no sign-off control (the first half holds), but no "L5 sign off…" menu item on EQR-required rows exists yet. Open: AUD-18's live host. |
| DV-8 | **Partly:** AUD-23 g names AUD-30 in its copy; no inline list, DOCX download or reference chip for FSP-06, XLA-02, AUD-28 or AUD-30 was found. Open until A-10, W-04 and Q-05 draw their targets. |

Copy: the L1–L12 copy lint (L2: verbatim from the handoff) runs over `screens/AUD-18/copy.ts` at the S36 end pass; no key changed in S36.
