---
id: SPEC-702
title: T-06 Entity return depth, relationships and hand-offs — TXP-03, TXP-04, TXP-08, TXP-09, TXP-13, TAX-11, CLI-03, AUD-38
status: approved
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-026, ADR-050, ADR-052, ADR-151, ADR-158, ADR-161, ADR-164, ADR-167, ADR-300, ADR-320, ADR-341]
related_specs: [SPEC-651, SPEC-700, SPEC-701]
created: 2026-11-17
updated: 2026-11-17
epic: T-06
task: T-06-T01 (TASK-8510)
---

# SPEC-702 · Entity return depth, relationships and hand-offs

> **Instructions for coding agents**
> - The design is `docs/plan/epics/T-06.md` §1 to §8; task rows `docs/plan/epics/T-06.tasks.csv`.
>   F1 to F9 are adopted verbatim; this file numbers their testable cores AC-1 to AC-36.
> - Screen contracts: `docs/screens/{TXP-03,TXP-04,TXP-08,TXP-09,TXP-13,TAX-11,CLI-03,AUD-38}.md`.
> - **Code computes, models judge** (ADR-050; DEC-77): Accrued computes workpaper figures only
>   (M-1/M-2/M-3, §752, PTET, AAA, sourcing, ASC 740 and 990 workpapers); the engine computes tax,
>   credits and filed forms; rounding by largest remainder.
> - Agents propose; people approve, send and hand off (INV-1). §7216 consent before every `tri`
>   agent read (C19). Walls are 404 with no count (DEC-43, DEC-88). Never transmit (R-04).

## 1. Summary
A reviewer sees Ridgeline's 2025 Form 1065 in depth (depreciation register, book-tax, basis and the
§754 decision, states and PTET) as exceptions on code's figures; 1120-S, 1120 and 990 returns get
their workpapers; an audited or closed TB lands as a return's starting TB through C12; a draft
form preview with K-1s shows blocking diagnostics before approval; and a relationships map shows
who owns what and which K-1s flow where.

## 2. Gate check (main aceddcbbf, 2026-11-17; DEC-5510)

| Decision | On main | State | T-06 use |
|---|---|---|---|
| DEC-77 computation boundary | ch09 + T-05 (SPEC-651) | decided | E3, E4, E8, E12 compute workpaper figures only |
| DEC-78 filed forms from the engine | ch09 | decided | TAX-11 previews from an approved checkpoint, "Draft — not for filing" (OQ-1 yes) |
| DEC-76 / P-62 reference data | ADR-300 | accepted | `tax/compute/parameters/ty20NN.yaml` (ty2027 on main; ty2025, ty2026, ty2028 in T-06-T13) |
| DEC-84 reviewer edits, re-approval | ch09 + T-05 | decided | ghost values, Re-approve… |
| DEC-88 K-1 hand-off across clients | ch09 | decided | edge visible only to readers of both engagements |
| DEC-32 + DF-02 CLI-03 from TPL-14 | ch09 | decided; the board (T-06-T68) is **not made** | CLI-03 composes TPL-14 a–f; T-06-T02 waits on the board |
| DEC-43 walls, DEC-62 client shape, DEC-66 ledger owns mappings | ch09 | decided | 404 nodes; `entity_relationships`; `tb_handoffs` in ledger |
| P-35 proposals and grants | ADR-161 | accepted | proposals, `seen_version`, Undo |
| P-12 §7216, TRI, TINs | ADR-167 | accepted | consent gate, masked TINs |
| P-18 never transmit | ADR-151 | accepted | no transmit control |
| P-19 deterministic documents | ADR-320 | accepted | C11 form faces |
| P-40 cross-engagement links | ADR-158 | accepted | the hand-off references the source snapshot |
| P-13 attest rules | ADR-164 | accepted | AUD-38 independence card |
| P-63 multi-entity engagements | ADR-341 | accepted | the relationships graph semantics below (§4) |

**What T-05 shipped that T-06 consumes** (paths on origin/main):
- DAG step stubs: `backend/src/abacus/modules/tax/entity_run_plan.py` (`depreciation_register`, `bonus_eligibility`, `apportionment_ptet`, `capital_m2`, `federal_k1s`, `state_k1s_k3s`) and `run_steps.py` (02 and 08 imported reports read in place of E3/E9; DEC-4703/4704).
- M-2 cells: `backend/src/abacus/modules/tax/compute/entity/capital.py` (`ScheduleM2`, the "off 6,200" tie to Schedule L line 21).
- Change sets and issues: `backend/src/abacus/modules/tax/entity_issues.py` (workbook tab → step map) and `compute/entity/tb_pipeline.py`.
- Parameters: `backend/src/abacus/modules/tax/compute/parameters/ty2027.yaml` (T-06-T13 adds the MACRS and bonus tables).

## 3. Open questions (epic §11.2; DEC-5510)
OQ-1 yes (DEC-78 closes chapter 01's renderer question) · OQ-2 Form 1065 pp 1–5, Schedule K-1 (1065), M-3, 8825, 4562 summary, §199A and §754 statements; other forms show "Preview available after export from the engine" · OQ-3 no gate in v1, amber independence card · OQ-4 yes, `review_release` gated by G8; compilation and preparation excluded · OQ-5 one renewal to the first Friday after Apr 20 · OQ-6 seniors and above plus `firm_admin` create; ending needs a manager or partner · OQ-7 no auto-create; TAX-15 pre-filled · OQ-8 ship as a composed TXP-04 b frame unless throughput slips (cut item 5) · OQ-9 `organisations.relationship_graph_layouts`, unaudited.

## 4. Relationships graph semantics (P-63 as a spec)
Nodes are clients, client entities and external parties; edges are `entity_relationships` (kinds:
owner, partner, member, shareholder, trustee, beneficiary, grantor, custodian, spouse, dependent,
k1_recipient) with a percent where the kind carries one. Ownership into one entity never exceeds
100% (deferred trigger). No self-edges. Edges end (ended_at, by, reason), never delete. A K-1 edge
is derived from T-02's packages, not stored. Walled nodes are omitted with no placeholder and no
count; a K-1 edge needs read on both engagements. Layouts are per user and unaudited.

## 5. Acceptance criteria
- **AC-1** TXP-03 a ties 2,625,167 = 1,891,667 + 733,500 to TB 1650 and 733,500 to TB 5600, from E3 with engine version and inputs hash (F1).
- **AC-2** By property foots land 3,600,000 and depreciation 169,500 + 360,000 + 204,000 = 733,500 to Form 8825 (F1).
- **AC-3** An asset change is a ghost value until a reviewer approves; approval checkpoints and re-runs only depreciation and K-1 steps (F1).
- **AC-4** A cited binding-contract date turns the bonus check to tie; without a citation it stays Check (F1, INV-2).
- **AC-5** Sign-off with an open flag needs a note (409 `open_flags_note_required`); later changes make it stale (F1).
- **AC-6** Dispositions classify recapture; an Accepted return answers 409 `return_locked` (F1).
- **AC-7** M-3 is required at 17,914,500, (a)+(b)+(c)=(d) on every row, one permanent row 6,200 (F2).
- **AC-8** The M-1 reference never marks both as filed; TAX-11 renders only M-3 (F2).
- **AC-9** M-2 drafted 6,860,000 vs Schedule L 6,866,200; the fix previews without writing (F2).
- **AC-10** Accept writes one human decision, a checkpoint and a capital/K-1 re-run; stale `seen_version` 409 `proposal_changed` (F2).
- **AC-11** Granite Peak's 1120 M-1 starts at 2,350,000 with 750,000 added back (F2).
- **AC-12** Basis: 4 of 5 reconciled; Jonah Feld 4,676,125; Pell Street II 885,225 vs 913,820 (F3).
- **AC-13** §752 shares 10,712,500 + 335,800 by profit percent; Jonah 2,762,075 matches Item K (F3).
- **AC-14** The §754 card's options are code's; the firm only sends it; a second send 409 `decision_already_sent` (F3).
- **AC-15** Only the decision owner contact sees the request (INV-4); the answer is the client's, never the agent's (F3).
- **AC-16** Apportionment 46.0 + 31.5 + 22.5 = 100.0; PTET 64,096 paid (F4).
- **AC-17** An unmapped property reads Map… and Check until mapped (F4).
- **AC-18** A missing payment raises one issue that recording the payment resolves (F4).
- **AC-19** Sourcing approval is human-only with three verified citations; the badge moves 11 → 10 → 9; Undo writes `sourcing.undone` (F4).
- **AC-20** Partner credits foot by largest remainder with the recorded override 16,025 (F4).
- **AC-21** NYC Recommend opens TAX-15 pre-filled; T-06 records no election (F4).
- **AC-22** 1120-S AAA 1,488,200, 70/30 per share per day; Accepted is read-only (F5).
- **AC-23** ASC 740: 2,134,650 + 122,550 = 2,257,200 at 28.9% ETR, rate reconciliation ties (F5).
- **AC-24** An unclassified difference is classified only by a reviewer; without consent zero gateway calls (F5).
- **AC-25** 990 Part IX 4,014,000 foots and crossfoots; program 80.0%, public support 87.4% (F5).
- **AC-26** No partnership vocabulary on 1120/990 frames, no "$" in statement grammar (F5).
- **AC-27** The hand-off is unavailable before G8 (409 `handoff_not_available`) (F6).
- **AC-28** Review accounts block Hand off until each is chosen; the preview foots 121 + 5 + 2 = 128 and 3,100,000 − 750,000 = 2,350,000 (F6).
- **AC-29** Hand off writes one immutable, human-only `tb_handoffs` version and notifies the tax team (F6).
- **AC-30** A changed audited TB supersedes v1; an archived source receives no write (F6).
- **AC-31** C-02's `close_lock` source lands identically (F6).
- **AC-32** TAX-11 renders from the approved checkpoint, watermarked, TINs masked; diagnostics link to existing issues idempotently (F7).
- **AC-33** Blocking diagnostics refuse final approval 409 `blocking_diagnostics`; draft download needs fresh MFA and is audited; nothing transmits (F7).
- **AC-34** CLI-03 omits walled nodes and cross-client K-1 edges without read on both, with no count (F8).
- **AC-35** Add relationship writes one row by a person; a self-edge or > 100% ownership answers 422; relationships end, never delete (F8).
- **AC-36** Agent modes refuse without both §7216 consents; the portal never receives the graph, draft K-1 values or previews (F9).

## 6. Task map
T03 bundle · T04 words · T05/T06 C12 · T07/T09 entity-depth stubs · T08 relationships stub · T10,
T11, T12 migrations · T13 E3 · later tasks per the epic §9.
