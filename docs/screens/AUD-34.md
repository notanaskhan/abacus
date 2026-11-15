# AUD-34 · Group scoping and component materiality · Harlow & Pike

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/group/scoping?tab=components|coverage|aggregation` (`?ov=decision` SHL-11) |
| Template and host frame | T2 cockpit (rail 330 + canvas 1036) with T6 grammar + SHL-11 decision card |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-34 Group scoping and component materiality - Harlow and Pike/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | A-09 · SPEC-658 · A-09-T04 (contract), A-09-T03 (stubs), A-09-T07 (scenarios), screen rows per A-09 §9 |
| Persona | Margaret Okonkwo (EP) on a, c, e, f; Omar Haddad on b, d |
| Flags | `group_audit` capability; `assurance.group_audit` |
| Priority | P0 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

6 artboards, all built.

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Blocked · partner view | Options from code: 5% × 4,800,000 = 240,000 (recommended, cited); 4% = 192,000; another benchmark | Mon Sep 14, 2026, 3:38 PM CT | E1 | D · **C locked** | planned · `aud34.a` |
| b | Manager view | Radios disabled "Only the engagement partner can decide group materiality."; Remind Margaret | Mon Sep 14, 2026, 3:10 PM CT | E1 | D · C report-only | planned · `aud34.b` |
| c | Decided | 240,000 · PM 180,000 · CT 12,000 with rationale; component PMs 135,000 · 105,000 · 54,000 · 90,000 = 384,000 (75% · 58% · 30% · 50%); rail "Complete · 3:40 PM"; Draft component instructions… | Mon Sep 14, 2026, 3:40 PM CT | E1 after decision | D · **C locked** | planned · `aud34.c` |
| d | Proposing | Planned-work picker on Real Estate with the agent's suggestion (specific procedures; 17% of assets) | Mon Sep 14, 2026, 2:55 PM CT | E1 | D · C report-only | planned · `aud34.d` |
| e | Coverage | Sales 100% (73,000,000); total assets 78% full scope (27,000,000 + 12,760,000 = 39,760,000 of 50,760,000), 22% specific procedures (8,400,000 + 2,600,000) | Mon Sep 14, 2026, 3:38 PM CT | E1 | D · C report-only | planned · `aud34.e` |
| f | Flag off | No Group band; Materiality opens AUD-07 | Mon Sep 14, 2026, 3:38 PM CT | E1 | D · C report-only | planned · `aud34.f` |
| loading | — | skeleton per the template's loading grammar | — | — | D | planned |
| error | — | the read failed: designed error with Retry | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3); portal scopes isolated (INV-4) | — | — | — | planned |
| capability off | — | `group_audit` off (entitlement ∧ rollout flags): the designed flag-off state, never blank | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/AUD-34/scenarios.ts` (A-09 §5.4, A-09-T07), derived from the Harlow & Pike slice's footing figures, never typed by hand. Copy keys are `aud34.<state>.<element>`.

## API

Every state reads this endpoint set (A-09 §4.3; stubs in A-09-T03):

- `GET /v1/audits/{wid}/group-scoping` · `…/export.xlsx` (`group_scoping.read`)
- `PUT /v1/components/{id}` (`component.edit`; 422 above group PM or on Analytical only)
- `POST /v1/audits/{wid}/decisions/group-materiality` (`group_materiality.propose`) → P-04 `POST /v1/decision-cards/{id}/decide` (`decision.decide`, reserved EP, rationale, fresh MFA) · `/notify` · `/analysis-requests`

Matrix actions from `permission-matrix/{ledger,adjustments,assurance,portal,connections}.yaml` (A-09-T02): every finalize, approve, post, decide, send and review is a named person's; agent, support and portal principals deny every firm write.

## Links

| From | To | Status |
|---|---|---|
| Decide… | SHL-11 | live |
| Draft component instructions… | AUD-35 a | live |
| Materiality (flag off) | AUD-07 | live |
| tooltip or toast inside kits/AUD34 Scoping | SHL-13 | designed (handoff link graph) |

## Notes

Coverage 78%, never 83%. No "significant component", no component PM at or above group PM, no PM for Operating Co., no materiality on any client surface, no donut. CoverageBar carries View as table.

## Deviations

- DV-4 CoverageBar is an A-09 L2 component with View as table until C-36 (F-08).
- DV-5 component PM is manager-entered with a code default from the firm allocation table.
- DV-8 Request more analysis… shows only where `workbench.assistant` is cleared.

## Acceptance

SPEC-658's criteria for this screen; each becomes a test named "AUD-34 acceptance: <criterion>".
