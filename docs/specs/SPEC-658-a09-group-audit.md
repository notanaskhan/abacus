---
id: SPEC-658
title: A-09 Group audit (SAS 149) — consolidation setup (AUD-32), consolidated TB and eliminations (AUD-33), group scoping (AUD-34), component auditors (AUD-35), the component auditor room (POR-23), five-entity mapping (AUD-31 a–e)
status: approved
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-014, ADR-027, ADR-031, ADR-040, ADR-050, ADR-052, ADR-078, ADR-089, ADR-090, ADR-111, ADR-136, ADR-139, ADR-140, ADR-141, ADR-145, ADR-146, ADR-148, ADR-150, ADR-151, ADR-160, ADR-161, ADR-163, ADR-166, ADR-169, ADR-179, ADR-187, ADR-230, ADR-236, ADR-320, ADR-341]
related_specs: [SPEC-580, SPEC-642, SPEC-657]
created: 2026-11-15
updated: 2026-11-15
epic: A-09
task: A-09-T01 (TASK-8051)
---

# SPEC-658 · Group audit (SAS 149)

> **Instructions for coding agents**
> - The design is `docs/plan/epics/A-09.md` §1 to §8; task rows are `docs/plan/epics/A-09.tasks.csv`.
>   The acceptance criteria below are the epic's §3 stories, numbered here (AC-n.m) and adopted as
>   the spec of record; where the epic and a line here differ, the epic wins and this is corrected.
> - Screen contracts: `docs/screens/AUD-32.md` … `AUD-35.md`, `POR-23.md` (32 artboards) and the
>   AUD-31 group rows in `docs/screens/AUD-31.md`. Contracts provided: C9 v2.1
>   `docs/contracts/ledger-consolidation.md`, C8 v1.1 (eliminations, in `adjustments.md`),
>   `docs/contracts/group-audit.md` (A-09-T03).
> - **Code computes, models judge** (ADR-050): levels, consolidated balances, ties, "off n",
>   attribution, coverage, component PM validation and every elimination amount are code's. The
>   agent proposes structure, mapping, eliminations and a materiality option; it never finalizes,
>   adopts, approves, posts, decides or sends (INV-1).
> - **X-06 / X-07:** USD only, ownership 100% (no NCI, no translation), three tiers at most, GAAS
>   nonissuer only. The database refuses a fourth tier or ownership other than 100.

## 1. Summary
One SAS 149 group audit from structure to component deliverables: Omar Haddad builds and
finalizes Harlow & Pike's five-entity, three-tier structure from uploaded or NetSuite-exported
trial balances (interim debits 187,860,000); Caleb Dunn maps 244 accounts; Omar approves and posts
six eliminations to the consolidation layer only (67,840,000 Dr = Cr; consolidated total assets
50,760,000; intercompany 0 after E4); Margaret Okonkwo decides group materiality as a reserved
decision (240,000 / PM 180,000 / CT 12,000); component PMs 135,000 · 105,000 · 54,000 · 90,000 sum
to 384,000 and each is below 180,000; Omar sends instructions to Pruett & Lang LLP, whose Renee
Pruett sees only Harlow & Pike Distribution, Inc. in a white-labelled room.

## 2. Gate check (main ae0055816, 2026-11-15; DEC-5036)
By P-ID against `docs/adr/backlog.md` and each ADR file's `status:` (the file wins).

| P-ID / decision | Subject | On main | State | What A-09 does |
|---|---|---|---|---|
| DEC-65 (ch01 §1.9) | SAS 149 go, Dec-2028 year-ends | ch09 row | decided | Ships behind `group_audit`; fallback upload TBs and manual eliminations |
| DEC-66 | Grouping and FS-line taxonomy owner | ch09 row | decided | `ledger` owns mappings and consolidation, dependency-free |
| DEC-67 | Component auditors | ch09 row | decided | `component_auditor` grant at `component` scope (both already in 0083's CHECKs) |
| P-63 | Multi-entity engagements and consolidation | ADR-341 | accepted | `engagement_entities` (0068 role `component`); consolidation in `ledger` |
| P-09 | Client identity, scoped grants | ADR-146 | accepted | `component` scope kind (0083, 0115) |
| P-06 | Generalised `visible()` | ADR-145 | accepted | Component reads |
| P-07 · P-35 | Review grammar · suggestions | ADR-160 · ADR-161 | accepted | Decision cards with reserved role; structure suggestion; 10-s Undo |
| P-42 | Generalised comments | ADR-236 | **proposed** (acceptance: Ayush) | `component_thread` anchor, share guard |
| P-17 | Integrations, write capabilities | ADR-150 | accepted | No W-entry for NetSuite; never "Post to NetSuite" |
| P-19 · P-24 · P-47 · P-48 | Documents · structured output · runs · citations | ADR-320 · ADR-230 · ADR-169 · ADR-166 | accepted | Letter PDF, AgentBlocks, run records, cell citations |
| P-28 · P-29 | Entitlements · busy season | ADR-148 · ADR-151 | accepted · proposed | `group_audit` entitlement; window rules |
| P-11 · P-54 | White-label portal · auth | ADR-163 · ADR-141 | accepted | Neutral host; code sign-in; MFA for component auditors (OQ-4) |
| P-14 | Retention | ADR-179 | proposed | Record types for consolidation, instructions, deliverables |
| P-08 | Policy principal, dormant | ADR-187 | accepted | No elimination accepted by a policy actor |
| P-25 | Model-drafted text to clients | not drafted | bounding | Template merges for real firms (DV-6, DV-7) |
| DF-31 · DF-37 · DF-40 | Status words · `link-2-off` · POR-20 templates | ch09 rows | decided | A-09-T04 rows; expired-room icon; templates as DB content |

**Open:** P-42 (ADR-236) and P-29 (ADR-151) are proposed; A-09 builds on them per
AMENDMENT-solo and leaves acceptance to Ayush (DEC-5036). DEC-70 keeps NetSuite on file import:
the fake OneWorld connector serves synthetic tenants only.

## 3. Open questions (epic §11.2) — the recommended answers (DEC-5036)
OQ-1 component PM is manager-entered with a code default from a firm-standard allocation table;
below group PM, none for Analytical only · OQ-2 reopening keeps AUD-34's decision; coverage facts
and consolidation sign-offs compute stale · OQ-3 one `proposed_entries` ledger with
`consolidation_id` · OQ-4 MFA mandatory for component auditors · OQ-5 the component grant expires
at the group report date + 60 days or at archive, renewable by the manager · OQ-6 recipient-aware
internal-terms filter (own component PM and CT allowed) · OQ-7 no structure change after finalize
in v1 · OQ-8 links use `to.AUD31()` · OQ-9 `connections_one_live_ledger` drops in the first train
after the window.

## 4. Scope
Five screens (32 artboards) plus inherited host states (AUD-31 a–e, AUD-02 h, AUD-01 g, AUD-06 g,
ENG-03 g, SHL-18 f, the Today Late item). Modules: `ledger`, `adjustments`, `connections`,
`identity`, `communications`, `agents` (red); `assurance`, `engagements`, `portal`,
`collaboration`, `notifications` (amber). Flags: entitlement `group_audit`; rollout
`ledger.consolidation`, `assurance.group_audit` (A-09-T09); variant flags for the two prompts.
Out of scope (epic §2.3): ENG-14, ADM-13, a live OneWorld connector, HOME-05 surfaces, INB-04,
NCI, translation, equity method, fund and governmental audits, PCAOB issuers, structure revision,
consolidated statements, ChartKit, signature envelopes for instructions.

## 5. Acceptance criteria
Invariants everywhere: INV-1 to INV-5 (epic §3).

### F0 · Contract, data and vocabulary (S45 rows)
- **AC-0.1 (T02)** The generated matrix tests deny the agent, support and portal principals every A-09 firm write; `component_room.read`, `component.instructions.acknowledge` and `component_deliverable.upload` allow only `component_auditor` with `scope_only`.
- **AC-0.2 (T04)** Codegen emits the new StrEnums and `status.gen.ts` words (consolidation, TB attachment, elimination, group materiality decision, planned work, instructions, deliverable, with portal client words); the copy lint rejects "significant component" and "Post to NetSuite".
- **AC-0.3 (T03)** Every stub operation answers 501 under one matrix action; typed fixtures foot 50,760,000 and 67,840,000 Dr = Cr.
- **AC-0.4 (T05)** Up/down/up passes with forced RLS; a fourth tier or ownership other than 100 is refused by the database; an update to a finalized structure fails.
- **AC-0.5 (T06)** Consumer suites fail when any seed total stops footing.
- **AC-0.6 (T07)** Every lettered artboard has a typed scenario; footing tests pass for 187,860,000, 244 accounts, 50,760,000 and component PMs summing to 384,000.
- **AC-0.7 (T08)** EntityTree, MilestoneTimeline and CoverageBar specimens render every state; EntityTree reorders by keyboard alone.

### F1 · Structure (AUD-32)
- **AC-1.1** Reporting currency USD only; level 4 or ownership ≠ 100 → 422 and a database refusal.
- **AC-1.2** A missing slot disables Next with its reason; finalize answers 409 `trial_balance_missing`.
- **AC-1.3** Finalize is a manager's or EP's human act (one `consolidation.finalized` event); the structure is frozen by trigger; five `TbMappingWorkflow` runs start.
- **AC-1.4** The structure proposal is a suggestion; nothing saves until Use structure or Edit.

### F2 · Trial balances (AUD-32 a, f)
- **AC-2.1** A "TB by subsidiary" CSV splits into one immutable snapshot per covered entity; an unknown subsidiary is a row problem.
- **AC-2.2** A second live ledger for a covered entity → 409 `entity_already_covered`.

### F3 · Mapping (AUD-31 a–e)
- **AC-3.1** 238 of 244 mapped (32 + 8 + 98 + 76 + 30), split 201 prior-year + 25 number range + 12 description; confidence words only.
- **AC-3.2** Confirming records one L1 per entity set in one unit of work; the agent cannot adopt or confirm.

### F4 · Consolidation and eliminations (AUD-33)
- **AC-4.1** Level 1: total assets 50,760,000; eliminations on assets (48,640,000); 67,840,000 Dr = Cr; NI 3,500,000; every column nets to zero.
- **AC-4.2** Level 2: 20,000,000 + 29,400,000 + 13,000,000 − 22,640,000 = 39,760,000; NI 4,760,000.
- **AC-4.3** An unbalanced elimination shows "Off 10,000" and approve answers 409 `unbalanced_entry`.
- **AC-4.4** Post targets `consolidation_layer` only; no entity snapshot or client ledger changes.
- **AC-4.5** Locked: edits disabled; Reopen needs a reason (manager or EP) and stales sign-offs.

### F5 · Scoping (AUD-34)
- **AC-5.1** Group materiality is the EP's reserved decision with rationale and fresh MFA; 240,000 / 180,000 / 12,000.
- **AC-5.2** Component PMs below group PM, none for Analytical only, sum 384,000.
- **AC-5.3** Coverage: sales 100%; total assets 78% full scope (39,760,000 of 50,760,000), 22% specific procedures.

### F6 · Component auditors (AUD-35)
- **AC-6.1** Instructions are a deterministic template merge; Send is a person's with a 10-s Undo and issues the component grant.
- **AC-6.2** Deliverable statuses Expected · Received · Reviewed, Late derived and never stored.
- **AC-6.3** Make reference raises an EP-reserved decision card, default No.

### F7 · Room (POR-23)
- **AC-7.1** The room shows only the granted component; every other component, the consolidation, eliminations, scoping and group materiality answer 404.
- **AC-7.2** Client words only (Due · ✓ You uploaded · Overdue · Returned); no agent named; "Accrued" nowhere.

### F8 · Late deliverables
- **AC-8.1** The daily sweep emits `component_deliverable.went_late` once; Today lists the item; the follow-up's author is the person who sent it.

## 6. Task map
S45: T01 this SPEC · T02 protected bundle (red) · T04 vocabulary and screen contracts · T03 stubs ·
T05 migration `ledger_consolidation` (red) · T06 consumer tests · T07 fixture scenarios · T08 L2
kits. S46–S50 as the epic's §9.

## 7. Deviations
DV-1 to DV-11 as the epic's §2.4, each recorded in its screen contract.
