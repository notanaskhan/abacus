# AUD-33 · Consolidated trial balance and eliminations · Harlow & Pike interim 8/31/2026

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/group/consolidated-tb?level=1|2&tab=<entity>|consolidated&drawer=eliminations|adjustments` |
| Template and host frame | T6 workbook grid in Focus layout + docked Eliminations drawer 420 |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-33 Consolidated trial balance - Harlow and Pike interim 8312026/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | A-09 · SPEC-658 · A-09-T04 (contract), A-09-T03 (stubs), A-09-T07 (scenarios), screen rows per A-09 §9 |
| Persona | Omar Haddad (Audit Manager) |
| Flags | `group_audit` capability; `ledger.consolidation` |
| Priority | P0 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

7 artboards, all built. No browser arithmetic: every total, tie and "off n" is the server's.

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Interim 8/31 · all posted | Total assets 28,600,000 + 20,000,000 + 29,400,000 + 13,000,000 + 8,400,000 − 48,640,000 = 50,760,000; NI 3,500,000; E1a 20,000,000 · E1b 26,000,000 · E2 18,000,000 · E3 240,000 · E4 2,400,000 · E5 1,200,000 = 67,840,000 Dr = Cr; E3 expanded | Mon Sep 14, 2026, 2:05 PM CT | E1 | D · **C locked** | planned · `aud33.a` |
| b | Proposed by the agent | Six Proposed cards (C-31 atoms); BALANCED and INTERCOMPANY "Pending"; Approve 6… | Mon Sep 14, 2026, 1:33 PM CT | E1 variant | D · C report-only | planned · `aud33.b` |
| c | Unbalanced | E3 credit 250,000 → "Off 10,000 · debits 240,000 ≠ credits 250,000"; E4 approved not posted → INTERCOMPANY "off 2,400,000", total assets 53,160,000 | Mon Sep 14, 2026, 2:05 PM CT | E1 variant | D · **C locked** | planned · `aud33.c` |
| d | Level 2 · Operating Co. | 20,000,000 + 29,400,000 + 13,000,000 − 22,640,000 = 39,760,000; NI 3,400,000 + 1,600,000 − 240,000 = 4,760,000 | Mon Sep 14, 2026, 2:05 PM CT | E1 | D · C report-only | planned · `aud33.d` |
| e | Adjustments | Empty state "No adjustments yet" + New adjustment; import from template hides without templates (DV-3) | Mon Sep 14, 2026, 2:05 PM CT | E1 | D · C report-only | planned · `aud33.e` |
| f | Locked | "Locked · Omar Haddad · 2:20 PM"; edits disabled; Reopen… with a reason | Mon Sep 14, 2026, 2:20 PM CT | E1 after lock | D · **C locked** | planned · `aud33.f` |
| g | Entity tab · Manufacturing | Single-entity mapped TB balancing to 86,000,000 (AUD-06 grammar) | Mon Sep 14, 2026, 2:05 PM CT | E1 | D · C report-only | planned · `aud33.g` |
| loading | — | skeleton per the template's loading grammar | — | — | D | planned |
| error | — | the read failed: designed error with Retry | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3); portal scopes isolated (INV-4) | — | — | — | planned |
| capability off | — | `group_audit` off (entitlement ∧ rollout flags): the designed flag-off state, never blank | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/AUD-33/scenarios.ts` (A-09 §5.4, A-09-T07), derived from the Harlow & Pike slice's footing figures, never typed by hand. Copy keys are `aud33.<state>.<element>`.

## API

Every state reads this endpoint set (A-09 §4.3; stubs in A-09-T03):

- `GET …/consolidations/{cid}/tb?level=&view=` (`consolidation.read`) · `GET …/export.xlsx` (`consolidation.export`)
- `GET|POST /v1/consolidations/{cid}/eliminations` · `PATCH /v1/proposed-entries/{id}` (`elimination.read` / `.edit`)
- `POST /v1/proposed-entries/{id}/approve` · `POST …/eliminations:approve` · `POST …/{id}/reject` (`elimination.approve`; 409 `unbalanced_entry`) · `POST …/{id}/post` (`elimination.post`)
- `POST /v1/consolidations/{cid}/eliminations/propose` (`elimination.propose_run`) · `POST …/adjustments` (`proposed_entry.create`)
- `POST …/consolidations/{cid}/lock` · `/reopen` (`consolidation.lock`)

Matrix actions from `permission-matrix/{ledger,adjustments,assurance,portal,connections}.yaml` (A-09-T02): every finalize, approve, post, decide, send and review is a named person's; agent, support and portal principals deny every firm write.

## Links

| From | To | Status |
|---|---|---|
| Number cell | SHL-09 provenance | live |
| Elimination tag | cells lit purple 360 ms (tracing) | live |
| Sign off… | SHL-12 | live |
| Entity tab | AUD-06 g | live |

## Notes

Never "Post to NetSuite", NCI or translation columns, "$", red row fills or zebra. Credits in parentheses #B13327 and as text. "Off 10,000" announced in a polite live region. Eliminations live in the consolidation, never in an entity snapshot or a client ledger.

## Deviations

- DV-3 AJE/RJE kinds come from C8, not ADM-13.

## Acceptance

SPEC-658's criteria for this screen; each becomes a test named "AUD-33 acceptance: <criterion>".
