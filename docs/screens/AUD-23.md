# AUD-23 · Report builder

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/report` · `?tab=` and `?dock=` in the URL; sheets and dialogs in local state |
| Template and host frame | T10 DocumentOnWell (structure 470 = structured choices; paper 896 = live report) · `Wave 2 - Audit Completion.dc.html` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-23 Report builder/` (README.md, spec.md; revision.md wins where present) |
| Epic and tasks | A-07 · stubs T05 · migration T08 · templates T16 · registrations T19 · service T27 · screen T34 · SPEC-644 |
| Manifest status | planned in the route manifest (final, A-07-T53, S36): built and live inside the AUD-02 cockpit, with no route of its own (DEC-195, DEC-3414) |

## States
Clock is the demo clock (DEC-27): CDT (UTC−5) until Sun Nov 1, 2026, CST (UTC−6) after. Snapshots
E0–E7 are the Northwind PY2025 completion timeline of A-07-T11's scenario.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | margaret-okonkwo | Tue Oct 6, 2026, 10:10 AM CDT | E2 | Draft v2 awaiting the EP | live (T27) |
| b | margaret-okonkwo | Wed Oct 7, 2026, 4:20 PM CDT | E2 | Approved: "Approved by Margaret Okonkwo · Oct 7, 4:20 PM"; "Go to issuance & release" | live (T27) |
| c | hannah-leclerc | illustrative | illustrative | Qualified: Opinion row "Decision required"; "Request partner decision…" | live (T27) |
| d | hannah-leclerc | illustrative | illustrative | Going concern on: disabled for Northwind, "AUD-19 concluded no substantial doubt" | live (T27) |
| e | hannah-leclerc | Tue Nov 10, 2026 CST | Lakeshore | Review mode (AR-C 90) | live (T27; AUD-26 with A-08) |
| f | hannah-leclerc | illustrative | illustrative | Compilation mode (AR-C 80) | live (T27; AUD-26 with A-08) |
| g | margaret-okonkwo | Fri Jan 15, 2027 CST | illustrative | Reissue: dual date, red-tint "Reissued report" | fixture-only (DV-9; live with Q-05) |
| h | hannah-leclerc | Tue Oct 6, 2026 CDT | interact | Generating (R2) | live (T27) |
| i | hannah-leclerc | Tue Oct 6, 2026 CDT | interact | Generated (R2): toast "… v2.docx generated · DRAFT"; "Open in Word" | live (T27) |
| j | hannah-leclerc | Wed Oct 7, 2026 CDT | interact | Out of date (R2): amber "Out of date · Update from data" | live (T27) |
| loading, not allowed, off | as AUD-02 | — | — | flag off (from A-07-T33): 404 and the C-20 state; 501 before | live |

Parity tier: Tier C on the locked artboards named in A-07-T48; Tier D on the T2/T10 geometry.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET …/report` · `…/versions` · `…/diff` · `…/reason-codes` | `AuditReportOut` | `report.read` | — |
| write | `PATCH …/report/choices` | `ReportChoiceIn` | `report.draft` | manager, senior; never free text; 409 `decision_required` |
| write | `POST …/report/request-decision` · `POST …/report/documents` (202) | opinion card; C11 draft | `report.request_decision` · `report.generate` | — |
| write | C3 `POST /v1/sign-offs {target: audit_report_version, level: L4}` | P-04 | `sign_off.l4` | EP approval |

Every endpoint is in `docs/contracts/audit-completion.md` (A-07-T04, T05); 501 until its task.

## Status
`audit_report`, `decision_card`, `generated_document`.

## Copy
"Approved by Margaret Okonkwo · Oct 7, 4:20 PM", "Go to issuance & release", "Decision required", "Request partner decision…", "AUD-19 concluded no substantial doubt", "Reissued report", "… v2.docx generated · DRAFT", "Open in Word", "Out of date · Update from data", "Request EQR…". Copy keys live in `apps/web/src/copy/aud-23.ts` with the screen task; the words are the handoff's.

## Deviations
- DV-4: "Request EQR…" while an EQR is required and not concurred (DF-05)
- DV-8: FSP-06 renders as an inline list until A-10; "Open in Word" downloads the DOCX until W-04
- DV-9: g Reissue fixture-only until Q-05

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 | AUD-01 | handoff link (A-01; status in the manifest) |
| Opens AUD-02 | AUD-02 | handoff link (A-01; status in the manifest) |
| Opens FSP-06 | FSP-06 | planned link (DV-8; inline list, chip or download until A-10) |
| Opens KNW-03 | KNW-03 | handoff link (K-01; status in the manifest) |
| Opens SHL-11 | SHL-11 | handoff link (P-04; status in the manifest) |
| Opens SHL-12 | SHL-12 | handoff link (P-04; status in the manifest) |
| Opens SHL-16 | SHL-16 | handoff link (P-04; status in the manifest) |

## Acceptance
- Every artboard letter above carries live, fixture-only or deferred with its owning task or epic.
- No agent-owned control carries Approve, Sign off, Release, Send, Post or Decide; final verbs are never optimistic (A-07-T44).

## Final status (A-07-T53, S36)

Built and **live** in the AUD-02 cockpit (`completionLetters.tsx` → `LiveReport`) behind `audits.letters`, except **g Reissue, fixture-only until Q-05** (DV-9); c, d and f are illustrative states built on fixtures.

| Artboard | Final status |
|---|---|
| a | built · live behind the flag |
| b | built · live behind the flag |
| c | built · live behind the flag |
| d | built · live behind the flag |
| e | built · live behind the flag |
| f | built · live behind the flag |
| g | fixture-only (DV-9, Q-05) |
| h | built · live behind the flag |
| i | built · live behind the flag |
| j | built · live behind the flag |

| Deviation | Evidence |
|---|---|
| DV-4 | **Not found in code:** `screens/AUD-23/copy.ts` has no "Request EQR…". Open, AUD-23 follow-up. |
| DV-8 | **Partly:** AUD-23 g names AUD-30 in its copy; no inline list, DOCX download or reference chip for FSP-06, XLA-02, AUD-28 or AUD-30 was found. Open until A-10, W-04 and Q-05 draw their targets. |
| DV-9 | `AUD-23` g Reissue stays on fixtures; the reissue path is Q-05's; applied. |

Copy: the L1–L12 copy lint (L2: verbatim from the handoff) runs over `screens/AUD-23/copy.ts` at the S36 end pass; no key changed in S36.
