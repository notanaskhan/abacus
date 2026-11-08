# AUD-19 · Completion (checklist · subsequent events · legal letters · going concern)

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/completion` · `?tab=` and `?dock=` in the URL; sheets and dialogs in local state |
| Template and host frame | T2 with Agent dock (rail 330 · canvas 696 segmented Checklist · Subsequent events · Legal letters · Going concern · dock 330) · `Wave 2 - Audit Completion.dc.html` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-19 Completion -checklist - subsequent events - legal letters - goin/` (README.md, spec.md; revision.md wins where present) |
| Epic and tasks | A-07 · stubs T04 · migration T07 · projector T22 · events, letters, going concern T23 · screen T25 · agent T32 (#4231, #4240) · SPEC-644 |
| Manifest status | planned (fixture with its screen task; live with A-07-T47) |

## States
Clock is the demo clock (DEC-27): CDT (UTC−5) until Sun Nov 1, 2026, CST (UTC−6) after. Snapshots
E0–E7 are the Northwind PY2025 completion timeline of A-07-T11's scenario.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc | Tue Oct 6, 2026, 9:30 AM CDT | E2 | 12 complete · 1 N/A · 5 open; "What blocks the report" card; only the rep letter tagged G7; two client-dependent, two due on the report date | live (T22) |
| a2 | hannah-leclerc | 9:30 AM CDT | interact | Sign off… blocked: SHL-12 lists the 5 open items and Marcus Delaney's L1 before Hannah's L3 | live (P-04 SHL-12) |
| b | hannah-leclerc | 9:30 AM CDT | `?tab=subsequent-events` | Procedures through Oct 6; two nonrecognized events (Note 11, Note 9); bring-down queued Oct 9 | live (T23) |
| c | hannah-leclerc | 9:30 AM CDT | `?tab=legal-letters` | Not applicable with a basis; "Request a legal letter…" | live (T23) |
| d | hannah-leclerc | 9:30 AM CDT | `?tab=going-concern` | Decided card read-only, "Reserved to Engagement Partner" | live (T23) |
| e | margaret-okonkwo | Mon Oct 26, 2026 CDT | Granite Peak | Going concern · Granite Peak: DSCR 1.32x against the 1.25x covenant; revolver matures Mar 2028 | live (T23) |
| f | hannah-leclerc | Fri Oct 9, 2026, 9:05 AM CDT | E3 | All clear: 17 of 17 with N/A excluded; "Nothing blocks the report — open Issuance & release" | live (T22) |
| loading, not allowed, off | as AUD-02 | — | — | flag off (from A-07-T33): 404 and the C-20 state; 501 before | live |

Parity tier: Tier C on the locked artboards named in A-07-T48; Tier D on the T2/T10 geometry.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET …/completion` | `AuditCompletionOut` (counts exclude N/A) | `completion.read` | — |
| write | `POST …/completion/items/{key}/not-applicable` · `/reopen` | `CompletionItemNaIn` | `completion.update` | manager; 409 `item_derived` on projected rows |
| read · write | `GET …/subsequent-events` · `POST`/`PATCH …/procedures` · `POST …/subsequent-events` | `SubsequentEventsOut` | `completion.read` · `subsequent_event.*` | manager, senior |
| read · write | `GET`/`PUT …/legal-letters` · `POST …/legal-letters/request` | `LegalLetterOut` | `completion.read` · `legal_letter.*` | manager, senior |
| read · write | `GET …/going-concern` · `POST …/request-decision` | `GoingConcernOut` | `completion.read` · `going_concern.request_decision` | decided only by the EP on the C3 card |

Every endpoint is in `docs/contracts/audit-completion.md` (A-07-T04, T05); 501 until its task.

## Status
`completion_item`, `subsequent_event`, `legal_letter`, `decision_card`.

## Copy
"12 of 17", "What blocks the report", "Nothing blocks the report — open Issuance & release", "Reserved to Engagement Partner", "Request a legal letter…", "Not applicable", "Sign off…". Copy keys live in `apps/web/src/copy/aud-19.ts` with the screen task; the words are the handoff's.

## Deviations
- DV-8: the AUD-28 link renders as a reference chip until Q-05
- DV-AUD-19-2 (A-07-T25, DEC-2815): blocker rows read each open item's title, gate tag and link
  or due date from the read; the handoff's separate blocker sentences are not on
  `AuditCompletionOut`, and the titles are the firm template's words.
- DV-AUD-19-3: the summary's "Checked by Accrued Agent · run #4231 · 9:12 AM" line is not drawn;
  run #4231 and the queued #4240 show as the cockpit dock's SHL-13 tool cards (narration arrives
  with A-07-T32's agent).
- DV-AUD-19-4: the going-concern card shows the question and options as product copy and the
  chosen option's detail from `GoingConcernOut.inputs`; Granite Peak's FS-audit wording of the
  question waits for a card question on the read.
- DV-AUD-19-5: copy lives in `screens/AUD-19/copy.ts`, as every built screen's does, not
  `copy/aud-19.ts`. The reads stay 501 on the live server until A-07-T47 wires them (fixture mode
  per the row).

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 | AUD-01 | handoff link (A-01; status in the manifest) |
| Opens AUD-07 | AUD-07 | handoff link (A-04; status in the manifest) |
| Opens AUD-08 | AUD-08 | handoff link (A-04; status in the manifest) |
| Opens AUD-16 | AUD-16 | handoff link (A-06; status in the manifest) |
| Opens AUD-17 | AUD-17 | handoff link (A-06; status in the manifest) |
| Opens AUD-18 | AUD-18 | handoff link (A-07; status in the manifest) |
| Opens AUD-20 | AUD-20 | handoff link (A-06; status in the manifest) |
| Opens AUD-21 | AUD-21 | handoff link (A-07; status in the manifest) |
| Opens AUD-22 | AUD-22 | handoff link (A-07; status in the manifest) |
| Opens AUD-24 | AUD-24 | handoff link (A-07; status in the manifest) |
| Opens AUD-28 | AUD-28 | planned link (DV-8; inline list, chip or download until Q-05) |
| Opens EBP-07 | EBP-07 | handoff link (A-05; status in the manifest) |
| Opens SHL-12 | SHL-12 | handoff link (P-04; status in the manifest) |
| Opens SHL-14 | SHL-14 | handoff link (P-04; status in the manifest) |
| Opens WB-09 | WB-09 | handoff link (P-09; status in the manifest) |

## Acceptance
- Every artboard letter above carries live, fixture-only or deferred with its owning task or epic.
- No agent-owned control carries Approve, Sign off, Release, Send, Post or Decide; final verbs are never optimistic (A-07-T44).
