# ADM-14 · Firm settings › Plan & usage

| Field | Value |
|---|---|
| Route and params | `/settings/plan` (T12 settings frame of ADM-01); `?dialog=request-more` (Dialog 440) |
| Template and host frame | T12 settings form, two fieldset columns 546 + 546; Dialog 440; banner 32h; toast |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ADM-14 Plan and usage/` (no `revision.md`); kit `kits/ADM Settings.dc.html` (st 14a–14f) |
| Epic and tasks | G-04 · SPEC-680 AC-26 to AC-43 · G-04-T06 (contract), T03 (stub and typed fixtures), T11 (API), T12 (alert evaluator), T13 (scenarios), T18 (screen), T21 (parity) |
| Persona | Grace Holloway (Firm Admin, billing contact); Margaret Okonkwo (Managing Partner) on e |
| Flags | `platform.plan_usage` |
| Priority | P2 |
| Manifest status | planned |
| Owner | notanaskhan (build, T12 kit); ayushkbhatia (service, design fidelity) |

## States

6 artboards, all built.

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Within plan | "Usage month Sep 15 – Oct 14, 2026 · day 17 of 30"; "14,920 of 20,000 included" 74.6% = 8,640 + 4,610 + 1,420 + 120 + 130; ticks 75 · 90 · 100%; "Next alert at 75% (15,000) · 80 agent-minutes away · included minutes reset Oct 15"; band chip "Metered by Accrued · 9:15 AM"; Plan & seats "46 of 46 used" Full; billing rates 7 + 7 + 11 + 19 + 2 = 46 (fake provider, synthetic firm); Granite Peak 1,240 of 1,500 (83%) "Alert sent Sep 30 · HL" | Thu Oct 1, 2026, 9:20 AM CT | Oct 1 ledger | D · **C locked** | planned · `adm14.a` |
| b | Near limit | 18,240 · 91.2% (amber past 90%); banner "90% of included agent-minutes used · alert sent Oct 9, 1:47 PM to Grace Holloway, Margaret Okonkwo and Felix Andersen"; helper "1,760 left until Oct 15 · 75% alert sent Oct 1, 11:06 AM" | Fri Oct 9, 2026, 4:30 PM CT | Oct 9 ledger | D · **C locked** | planned · `adm14.b` |
| c | Over | 20,860 · 104.3%, red overflow; banner "860 agent-minutes over included · agents keep running (setting: Keep agents running) · overage is billed on the next invoice at the order-form rate" (no amount, P-27) | Wed Oct 14, 2026, 5:00 PM CT | Oct 14 ledger | D · **C locked** | planned · `adm14.c` |
| d | Dirty | At 100% → "Pause scheduled agents only"; "Unsaved changes"; Save enabled; amber-ink helper; toast "Plan & usage saved" after fresh MFA | Thu Oct 1, 2026, 9:20 AM CT | Oct 1 ledger | D · **C locked** | planned · `adm14.d` |
| e | Partner read-only · Margaret | banner "Only firm admins can change alerts and billing contact."; Locks on each band; Request more… enabled | Thu Oct 1, 2026, 9:14 AM CT | Oct 1 ledger | D · **C locked** | planned · `adm14.e` |
| f | Request more | Dialog 440: Seats 46 → 48 prorated to Jan 1, 2027 · Agent-minutes 20,000 → 30,000 from Oct 15 · Modules; Reason; "Partner approval: Margaret Okonkwo" | Thu Oct 1, 2026, 9:20 AM CT | Oct 1 ledger | D · **C locked** | planned · `adm14.f` |
| hidden | — | `security_admin` (Felix): the section row is hidden; a direct URL renders not-allowed with no data (ADM-01e) | — | — | — | planned |
| new tenant | — | no usage yet: meter at 0 with the helper | — | — | D | planned |
| not connected | — | a real firm before I-04: Billing rates Lock "Not connected · Connect CCH Axcess Practice" → `?ov=connection:cch-axcess-practice` (DV-2) | — | — | D | planned |
| conflict | — | 409 `stale_version` on Save: the designed reload prompt | — | — | D | planned |
| flag off | — | `platform.plan_usage` off: the section row is hidden and G-01's Plan & seats fieldset stays | — | — | — | planned |

Fixture scenarios: `apps/web/src/fixtures/scenarios/plan-usage.ts` (G-04-T13) from `platform/g04_fixtures.py` (every figure computed). Copy keys `adm14.<state>.<element>`.

## API

`docs/contracts/plan-usage.md`: `GET /v1/firm/plan`, `PUT …/billing-contact`, `GET · PUT /v1/firm/budget-alerts`, `GET /v1/firm/engagement-budgets?alerting=true`, `GET /v1/firm/billing-rates`, `GET · POST /v1/firm/plan-requests`, `…/approve`, `…/decline`, `…/withdraw`; `GET /v1/firm/usage` (P-10, additive). Actions `plan.read`, `budget_alert.manage` (fresh MFA), `billing_contact.manage`, `plan_request.create`, `plan_request.approve` (partner, fresh MFA, never the requester), `usage.read`.

## Links

| From | To | Status |
|---|---|---|
| Workbench active, 30 days › | INS-02 | planned (I-03) |
| Engagement row | ENG-06 | planned (I-04) |
| Connect CCH Axcess Practice | WB-11 `?ov=connection:cch-axcess-practice` | live after W-01 |
| Request more… / ADM-01 Add seats | one `seats` plan request | planned (T18) |

## Notes

No prices, credits, tokens, gauges, charts or per-person leaderboard; agent-minutes never read as hours (AC-31, the copy lint). Engagement rows go through `visible()` with no hidden counts (DEC-43).

## Deviations

| ID | Deviation | Decision | Owner |
|---|---|---|---|
| DV-1 | Modules list every held module (six for Brightwater) on ADM-14e and PLT-01b alike (OQ-7) | DEC-5200 OQ-7 | ayushkbhatia |
| DV-2 | Billing rates come from a provider slot: the synthetic-only fake now, CCH Axcess Practice through I-04; a real firm before then sees "Not connected" | DEC-5206 | ayushkbhatia |
| DV-3 | The design's "Default engagement budget" picker edits the firm default only; per-engagement overrides are ENG-06 (I-04, AC-39) | DEC-5206 | ayushkbhatia |

## Acceptance

SPEC-680 AC-26 to AC-43 for this screen; each becomes a test named "ADM-14 acceptance: <criterion>". Design-fidelity sign-off: Ayush.
