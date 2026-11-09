# T-04 gate check and kickoff · S32 Contract Monday (Mon Jan 10, 2028; run 2026-11-09)

T-04-T01 (TASK-6316; DEC-3016). Checked against main fcbfba3fc plus the S32 batch held for merge
(C17 freezes in P-10-T22, #1494). ADR numbers as `docs/adr/backlog.md` mints them.

## Gating ADRs
| Decision | ADR | Status on main | Gate |
|---|---|---|---|
| DEC-77 tax computation boundary (P-68) | ADR-231 | accepted (T-02-T36) | met |
| DEC-52 §7216 (P-12) | ADR-167 | accepted | met |
| DEC-36 review grammar (P-07) | ADR-160 | accepted | met |
| DEC-24, DEC-28 suggestions and grants (P-35) | ADR-161 | accepted | met |
| Citation v2 (P-48) | ADR-166 | accepted | met |
| DEC-42 OCR (P-32) | ADR-321 | accepted | met |
| DEC-41 capability specs (P-22) | ADR-233 | **proposed** (acceptance: ayushkbhatia) | **open** |
| DEC-41 gateway conversations (P-46) | ADR-234 | **proposed** (acceptance: ayushkbhatia) | **open** |
| DEC-41 structured agent output (P-24) | ADR-230 | accepted | met |

ADR-233 and ADR-234 are built against (P-10-T19 to T23 implement them) but their acceptance is
Ayush's. T-04's contract work (T02 to T07) does not depend on them; T-04-T19, T25, T31, T37 and T38
(converse, tools, the assistant) do. Until accepted those rows stay behind this gate.

## Upstream seams and contract suites
| Contract | State | Gate |
|---|---|---|
| T-01 seams (C19, `tax-engine-bridge.md`, `efile-record.md`) | frozen at v1 (T-01-T53) | met |
| T-02 seams (`tax-returns.md`, `k1-packages.md`) | frozen at v1 (T-02-T35) | met |
| C3 review grammar | services v1 frozen (P-04-T27) | met |
| C4 citations v1.1 | stub, v1 frozen; v1.1 additions land with P-03's live viewer | met for the stubs |
| C6 agent runs v2 | frozen (P-10-T16) | met |
| C17 tool registry | frozen at v1 in this batch (P-10-T22) | met at merge |
| C19 consent gate | frozen at v1 | met |
Suites are green in their providers' CI as of main's last green runs; the S32 end pass re-runs
them with this batch.

## P-10 Q1
Decided with the plan's default: T-04 declares its own `tax.assistant` loop spec on P-10's harness
and owns its evals; W-02 keeps it separate in 2028 (W-02 Q5). DEC-3016.

## Open questions Q1–Q12 (decision records with the recommended answers)
Recorded in `docs/product/decision-log.md` (DEC-3016) with the epic's recommended answers; each is
revisited by the sprint named in T-04 §11:
Q1 SHL-10 proposal for Confirm residency · Q2 inline E7 ApprovalCard with 10 s Undo · Q3 one
approval row per level, viewer's level from their work-item function · Q4 a release changing an
approved treatment marks it stale and raises an issue · Q5 NYC line 47a is an engine import only ·
Q6 drop the bracket-portion sentence unless a labelled shadow fact exists · Q7 TAX-07 events for the
return team with `tax_return.read`, walled 404 · Q8 Verified not required in v1 · Q9 2-Year
Comparison hidden until T-08 · Q10 real-firm shadow on CCH-imported values · Q11 saved prompts
hidden until W-03 · Q12 draft-run entry by triggers and a staff-only route.
(GitHub decision issues are not opened from this session; the decision log is the record.)

## Freeze touch points (live path) and their trains
| Touch point | Train |
|---|---|
| `permission-matrix/tax.yaml` rows (T-04-T03) | protected bundle, Jan 13 |
| status registry rows and codegen (T-04-T04) | Jan 13 |
| RW-1 and WS-1 stub routes behind `tax.review_workspace` / `tax.individual_workpapers` (T05) | Jan 20 |
| flags (T-04-T09) | Jan 27 |
| TAX-02 draft-run button (Q12) | Apr 27 |
Everything else in T-04 is additive and dark behind its flags until the post-window flip.
