# AUD-32 · Consolidation setup · Harlow & Pike FY2026

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId?ov=consolidation-setup[:<step>]` (steps details · structure · trial-balances · review) |
| Template and host frame | O6 stepper wizard on O4 geometry over AUD-02 (scrim) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-32 Consolidation setup - Harlow and Pike FY2026/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | A-09 · SPEC-658 · A-09-T04 (contract), A-09-T03 (stubs), A-09-T07 (scenarios), screen rows per A-09 §9 |
| Persona | Omar Haddad (Audit Manager) |
| Flags | `group_audit` capability; `ledger.consolidation` |
| Priority | P0 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

6 artboards, all built. f is synthetic-only until a live OneWorld connector exists (DV-1).

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Trial balances · 1 missing | 9 of 10 attached; + Add menu open on Real Estate · Prior; Next disabled "Add Real Estate's prior trial balance or mark it not needed" | Mon Sep 14, 2026, 10:44 AM CT | E1 | D · **C locked** | planned · `aud32.a` |
| b | Details | FY2026 group consolidation; year end 12/31/2026; USD; interim 8/31/2026 · 8 months; prior 12/31/2025; source NetSuite OneWorld (connected, read-only); labels Standard · Interim · Prior · Budget · Preliminary | Mon Sep 14, 2026, 10:31 AM CT | E1 | D · C report-only | planned · `aud32.b` |
| c | Structure | Agent-proposed 3 tiers from the 5 OneWorld subsidiaries (suggestion; Use structure · Edit); ownership 100% | Mon Sep 14, 2026, 10:36 AM CT | E1 | D · C report-only | planned · `aud32.c` |
| d | Review | 5 entities · 3 tiers · 10 TBs · all balanced; interim debits 30,760,000 + 20,000,000 + 86,000,000 + 42,400,000 + 8,700,000 = 187,860,000; Finalize (Manager) | Mon Sep 14, 2026, 10:47 AM CT | E1 | D · **C locked** | planned · `aud32.d` |
| e | Finalized | Toast "Consolidation finalized · 5 entities · trial balance mapping started"; rail Structure ✓ "Finalized · 10:48 AM"; AUD-31 b running | Mon Sep 14, 2026, 10:48 AM CT | E1 | D · C report-only (toast masked) | planned · `aud32.e` |
| f | Pull failed | Distribution Interim "Needs reauth"; Request reconnection… → POR-16 (Nadine Brooks) | Mon Sep 14, 2026, 10:44 AM CT | E1 variant | D · C report-only | planned · `aud32.f` (synthetic-only) |
| loading | — | skeleton per the template's loading grammar | — | — | D | planned |
| error | — | the read failed: designed error with Retry | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3); portal scopes isolated (INV-4) | — | — | — | planned |
| capability off | — | `group_audit` off (entitlement ∧ rollout flags): the designed flag-off state, never blank | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/AUD-32/scenarios.ts` (A-09 §5.4, A-09-T07), derived from the Harlow & Pike slice's footing figures, never typed by hand. Copy keys are `aud32.<state>.<element>`.

## API

Every state reads this endpoint set (A-09 §4.3; stubs in A-09-T03):

- `POST /v1/audits/{wid}/consolidations` · `GET`/`PATCH`/`DELETE …/consolidations/{cid}` (`consolidation.edit` / `.read`)
- `PUT …/structure` · `POST …/structure/proposal` (`consolidation.edit`)
- `POST …/entities/{ceid}/trial-balances` · `POST …/trial-balances/{tbid}/not-needed` · `POST …/bulk-upload` · `POST …/pull-all` (`consolidation.edit`)
- `POST …/finalize` (`consolidation.finalize`; 409 `trial_balance_missing`)

Matrix actions from `permission-matrix/{ledger,adjustments,assurance,portal,connections}.yaml` (A-09-T02): every finalize, approve, post, decide, send and review is a named person's; agent, support and portal principals deny every firm write.

## Links

| From | To | Status |
|---|---|---|
| Request reconnection… | POR-16 (client) | live |
| Finalize | AUD-31 b | live |
| + Add → From Source Docs | AUD-03 | live |
| tooltip or toast inside kits/AUD32 Consolidation | SHL-08 | designed (handoff link graph) |
| tooltip or toast inside kits/AUD32 Consolidation | AUD-33 | designed (handoff link graph) |

## Notes

Finalize is espresso, never green. "From NetSuite connection" and "Pull all from NetSuite…" render only where a OneWorld connection covers the entities (DV-1). Ownership is fixed at 100% and three tiers at most (X-06). Every total debit is the server's.

## Deviations

- DV-1 connection items render only with a covering OneWorld connection (fake on synthetic tenants).
- DV-2 the structure proposal is deterministic and attributed Accrued Agent as a P-35 suggestion.
- DV-3 labels come from A-02's label set, not ADM-13.

## Acceptance

SPEC-658's criteria for this screen; each becomes a test named "AUD-32 acceptance: <criterion>".
