# POR-23 · Group audit · Harlow & Pike Distribution, Inc. (component auditor room)

| Field | Value |
|---|---|
| Route and params | Portal `/component-room`, `/component-room/instructions` (reader with Download PDF) |
| Template and host frame | T7 reduced (single centered pane 720; POR-14 grammar) + T7-M |
| Surface | portal (component auditor, white-labelled) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-23 Group audit - Harlow and Pike Distribution- Inc/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | A-09 · SPEC-658 · A-09-T04 (contract), A-09-T03 (stubs), A-09-T07 (scenarios), screen rows per A-09 §9 |
| Persona | Renee Pruett (Pruett & Lang LLP) |
| Flags | `group_audit` capability for the firm; the `component_auditor` grant |
| Priority | P0 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

6 artboards, all built. T7-M 390 from spec text at Tier D only (DV-9).

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Invited | Instructions to acknowledge; 0 of 4; header "Harlow & Pike Holdings, Inc. · FY2026 group audit" over "Component: Harlow & Pike Distribution, Inc." | Wed Sep 23, 2026, 9:40 AM CT | E1 | D · **C locked** | planned · `por23.a` |
| b | Acknowledged, with a question | "✓ You acknowledged Sep 23"; Omar's answer | Wed Sep 23, 2026, 11:20 AM CT | E1 | D · **C locked** | planned · `por23.b` |
| c | Deliverable overdue | 1 of 4; interim memo Overdue; Margaret's follow-up | Tue Dec 1, 2026, 9:05 AM CT | E1 | D · C report-only | planned · `por23.c` |
| d | Uploaded | 2 of 4; "✓ You uploaded Dec 2 · Brightwater Hale is reviewing it" | Wed Dec 2, 2026 | E1 | D · C report-only | planned · `por23.d` |
| e | Returned | "Returned · not signed" + Omar's note | Wed Sep 23, 2026, 9:40 AM CT | E1 variant | D · C report-only | planned · `por23.e` |
| f | Invitation expired | EmptyState with `link-2-off` | — | E1 variant | D · **C locked** | planned · `por23.f` |
| loading | — | skeleton per the template's loading grammar | — | — | D | planned |
| error | — | the read failed: designed error with Retry | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3); portal scopes isolated (INV-4) | — | — | — | planned |
| capability off | — | `group_audit` off (entitlement ∧ rollout flags): the designed flag-off state, never blank | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/POR-23/scenarios.ts` (A-09 §5.4, A-09-T07), derived from the Harlow & Pike slice's footing figures, never typed by hand. Copy keys are `por23.<state>.<element>`.

## API

Every state reads this endpoint set (A-09 §4.3; stubs in A-09-T03):

- `GET /v1/portal/component-rooms/{id}` · `…/instructions` (+ `/pdf`) (`component_room.read`)
- `POST …/instructions/acknowledge` (`component_instructions.acknowledge`, MFA)
- `GET …/deliverables` · `POST …/deliverables/{did}/uploads` · `POST …/drops` (`component_room.read` / `component_deliverable.upload`)
- `GET|POST …/questions` (`component_room.ask`; P-05 share guard)

Matrix actions from `permission-matrix/{ledger,adjustments,assurance,portal,connections}.yaml` (A-09-T02): every finalize, approve, post, decide, send and review is a named person's; agent, support and portal principals deny every firm write.

## Links

| From | To | Status |
|---|---|---|
| Group audit (one nav item) | the room | live |

## Notes

One nav item "Group audit"; "Accrued" nowhere; client words Due · ✓ You uploaded · Overdue · Returned; no agent named; firm-only words (Expected, Reviewed, Late), initials, review notes and agent reasoning never render. Every other component, the consolidation, eliminations, scoping and group materiality answer 404 (INV-4). The drop zone has an Upload… button; the letter is HTML text with a PDF download.

## Deviations

- DV-9 T7-M 390 from spec text at Tier D only.
- DV-10 questions appear on AUD-35's thread.

## Acceptance

SPEC-658's criteria for this screen; each becomes a test named "POR-23 acceptance: <criterion>".

## A-09-T36 (states a–f, DEC-5523)
Fixture scenarios a–f (`fixtures/scenarios/POR-23.ts`, Renee Pruett): a invited (Sep 23, 9:40 AM), b acknowledged with a question (11:20 AM), c interim memo overdue (Dec 1, 9:05 AM), d uploaded (Dec 2), e returned, f invitation expired. The seed's four deliverables are now the handoff's (Planning confirmation Oct 2; Interim memo Nov 30; Clearance memo, summary of uncorrected misstatements and component trial balance Feb 12, 2027; Subsequent events update Mar 19, 2027).

| Where | Handoff | Built | Why |
|---|---|---|---|
| Intro team line | "Group engagement partner Margaret Okonkwo · Manager Omar Haddad" | omitted | the room read model carries no firm people (A-09-T33's allowlist); a later read-model field |
| Empty thread | "Questions go to Omar Haddad and Margaret Okonkwo." | "Questions go to Brightwater Hale LLP." | same |
| d uploaded sub-line | "✓ You uploaded Dec 2 · Brightwater Hale is reviewing it" | "✓ You uploaded Dec 2" | the client word is `you_uploaded` for received and reviewed alike (client words only) |
| Letter preview | first page with a fade, "Page 1 of 6" | sections in full, "Open the full letter ›" opens the reader with Download PDF | the instructions arrive as sections, not page images |
