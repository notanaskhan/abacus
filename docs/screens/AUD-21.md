# AUD-21 · Representation letter builder

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/representation-letter` · `?tab=` and `?dock=` in the URL; sheets and dialogs in local state |
| Template and host frame | T10 DocumentOnWell (structure 470 + paper 896, paper card 600) · `Wave 2 - Audit Completion.dc.html` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-21 Representation letter builder/` (README.md, spec.md; revision.md wins where present) |
| Epic and tasks | A-07 · stubs T05 · migration T08 · templates T12 · registrations T19 · service T24 · screen T28 · agent T32 · SPEC-644 |
| Manifest status | planned in the route manifest (final, A-07-T53, S36): built and live inside the AUD-02 cockpit, with no route of its own (DEC-195, DEC-3414) |

## States
Clock is the demo clock (DEC-27): CDT (UTC−5) until Sun Nov 1, 2026, CST (UTC−6) after. Snapshots
E0–E7 are the Northwind PY2025 completion timeline of A-07-T11's scenario.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc | Tue Oct 6, 2026, 8:50 AM CDT | E2 | Draft · partner-approved: v3 approved by Margaret Okonkwo Oct 5 5:10 PM | live (T24) |
| a2 | hannah-leclerc | 8:50 AM CDT | interact | Send for signature… through the SIG-02 overlay: Dana Kowalski signs first and only; date fixed to the report date | live (T24, N-02) |
| b | hannah-leclerc | Mon Oct 5, 2026, 2:30 PM CDT | E1 | Awaiting partner approval: v2 | live (T24) |
| c | hannah-leclerc | Tue Oct 6, 2026, 11:40 AM CDT | E2 | Sent · viewed ("Viewed Oct 6, 11:02 AM"); letter locked | live (T24) |
| d | hannah-leclerc | Fri Oct 9, 2026, 9:20 AM CDT | E3 | Signed · G7: "Dated October 9, 2026 = report date ✓ · G7" | live (T24) |
| e | hannah-leclerc | Thu Oct 8, 2026 CDT | illustrative | Date mismatch: "Start re-date…" | live (T24) |
| f | hannah-leclerc | Fri Oct 2, 2026, 8:20 AM CDT | E0 | Drafting: skeleton and the agent narration | live (T24, T32) |
| loading, not allowed, off | as AUD-02 | — | — | flag off (from A-07-T33): 404 and the C-20 state; 501 before | live |

Parity tier: Tier C on the locked artboards named in A-07-T48; Tier D on the T2/T10 geometry.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET …/representation-letter` · `…/versions[/{v}]` | `RepresentationLetterOut` | `rep_letter.read` | — |
| write | `POST …/compose` (202) · `PATCH …/representations/{key}` · `PUT …/paragraphs/{key}` | toggles and firm-editable paragraphs | `rep_letter.draft` | manager, senior; agent drafts read "‹person› via Agent" |
| write | `POST …/request-approval` · `POST …/versions/{v}/approve` | `LetterApproveIn` (step-up) | `rep_letter.request_approval` · `rep_letter.approve` | EP approves; human only |
| write | `POST …/send` · `/remind` · `/re-date` (Idempotency-Key) | `LetterSendIn` | `rep_letter.send` · `envelope.remind` | manager, EP; 409 `approval_required` before approval |

Every endpoint is in `docs/contracts/audit-completion.md` (A-07-T04, T05); 501 until its task.

## Status
`representation_letter`, `envelope`.

## Copy
"Always included", "Send for signature…", "Viewed Oct 6, 11:02 AM", "Dated October 9, 2026 = report date ✓ · G7", "Dated October 8, 2026 ≠ report date October 9", "Start re-date…", "Accrued Agent is drafting from the findings register (9 findings) and the SUM". Copy keys live in `apps/web/src/copy/aud-21.ts` with the screen task; the words are the handoff's.

## Deviations
- DV-1: signer identity "Email code" (DF-11; KBA only for the 8879 family)
- DV-5: general toggles map to paragraphs 1–11 (locked, "Always included"), specific to 12–15 (DF-27)

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 | AUD-01 | handoff link (A-01; status in the manifest) |
| Opens AUD-02 | AUD-02 | handoff link (A-01; status in the manifest) |
| Opens AUD-15 | AUD-15 | handoff link (A-06; status in the manifest) |
| Opens AUD-16 | AUD-16 | handoff link (A-06; status in the manifest) |
| Opens AUD-17 | AUD-17 | handoff link (A-06; status in the manifest) |
| Opens AUD-19 | AUD-19 | handoff link (A-07; status in the manifest) |
| Opens AUD-20 | AUD-20 | handoff link (A-06; status in the manifest) |
| Opens AUD-24 | AUD-24 | handoff link (A-07; status in the manifest) |
| Opens CLI-04 | CLI-04 | handoff link (P-07; status in the manifest) |
| Opens EBP-07 | EBP-07 | handoff link (A-05; status in the manifest) |
| Opens ENG-02 | ENG-02 | handoff link (P-07; status in the manifest) |

## Acceptance
- Every artboard letter above carries live, fixture-only or deferred with its owning task or epic.
- No agent-owned control carries Approve, Sign off, Release, Send, Post or Decide; final verbs are never optimistic (A-07-T44).

## Final status (A-07-T53, S36)

Built and **live** in the AUD-02 cockpit (`completionLetters.tsx` → `RepLetterLive`) behind `audits.letters`; no route of its own (path null).

| Artboard | Final status |
|---|---|
| a | built · live behind the flag |
| a2 | built · live behind the flag |
| b | built · live behind the flag |
| c | built · live behind the flag |
| d | built · live behind the flag |
| e | built · live behind the flag |
| f | built · live behind the flag |

| Deviation | Evidence |
|---|---|
| DV-1 | `screens/AUD-21` envelope identity reads "Email code" (SIG-02 prefill); applied. |
| DV-5 | `screens/AUD-21` structure maps general toggles to paragraphs 1–11 (locked) and specific toggles to 12–15; applied. |

Copy: the L1–L12 copy lint (L2: verbatim from the handoff) runs over `screens/AUD-21/copy.ts` at the S36 end pass; no key changed in S36.
