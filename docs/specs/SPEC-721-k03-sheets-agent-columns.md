---
id: SPEC-721
title: K-03 Sheets engine and agent columns (SHT-01, SHT-02, SHT-04)
status: approved
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-050, ADR-066, ADR-133, ADR-144, ADR-146, ADR-147, ADR-148, ADR-156, ADR-161, ADR-213, ADR-233, ADR-234, ADR-345]
related_specs: [SPEC-720]
created: 2026-11-20
updated: 2026-11-20
epic: K-03
task: K-03-T03 (TASK-8802)
---

# SPEC-721 · Sheets engine and agent columns

> **Instructions for coding agents**
> - The design is `docs/plan/epics/K-03.md` §3.7–§3.13 and §6, adopted verbatim; this file numbers
>   their testable cores AC-1 to AC-30.
> - Screen contracts `docs/screens/{SHT-01,SHT-02,SHT-04}.md`; module contract
>   `docs/contracts/sheets.md` (C23, SH-1); view model `SheetVM` (F-08 §4).
> - **The agent never adopts, signs, saves a column or raises an exception** (INV-1). Agent columns
>   produce cited suggestions only; a named person adopts them by signing the row off.
> - Firm instructions enter as `<firm_instruction>` after the registered prompt (ADR-345).

## 1. Summary
On Granite Peak the BH-FS-430 sheet is created empty from FS v5, filled from the approved 40-item
sample (two strata, 3,698,700.00), extended with a Service period column, and tested by the
Conclusion agent column, which a senior previews on three rows and a manager saves. Cole signs the
rows off as preparer, which adopts the suggestions; Hannah corrects one and signs off as reviewer,
which locks the sheet.

## 2. Acceptance criteria

### Create, fill, edit, views (SHT-01 a, b, c, f)
- **AC-1** Procedure to in progress creates an empty sheet from FS v5: EmptyState "No rows yet",
  "0 rows · View: Default", no Service period column.
- **AC-2** Rows from the approved sample (seed `0x7C31B4`): "STRATUM 1 — PAYMENTS ≥ $50,000 (24)"
  3,286,400.00 and "STRATUM 2 — RANDOM, $7,750–$49,999 (16)" 412,300.00; status bar "40 rows ·
  0 tested · seed 0x7C31B4"; totals by code.
- **AC-3** Cell edits go through `review.api.record_value` with the row version (412 on conflict).
- **AC-4** Views Default · Exceptions (1) · Above $50,000 (24) are server-stored and URL-addressable.
- **AC-5** "Open in Excel" downloads a deterministic xlsx (byte-identical on re-export); client text
  cells are escaped (`safe_text`).

### Columns (SHT-02 a–f)
- **AC-6** Eleven column types: text, long text, number, currency, date, date range, single select,
  multi select, person, evidence link, agent.
- **AC-7** Hannah adds Service period (Date range, month display, Required, Restricted) after
  Invoice date; toast "Service period added · logged in Activity"; audit event written.
- **AC-8** Deleting a column used by 2 views and an agent column answers 409 `column_in_use`;
  dialog "Deleting a column never removes evidence or sign-offs."
- **AC-9** Date → Text shows the impact warning first; 40 values convert by code.
- **AC-10** Lowering a client-data column below Restricted without a reason answers 422; on an
  internal sheet "Visible to client" is disabled.
- **AC-11** Simone or Cole: read-only drawer "Only managers can add or change columns." and
  "Suggest to Hannah Leclerc…" posts a mention.

### Sign-off, adoption, lock (SHT-01 e, f; SHL-12)
- **AC-12** SURL-05's Why card shows the first-person reason and two verified citation chips.
- **AC-13** Cole's preparer sign-off adopts each row's pending suggestions in the same unit of work
  ("adopted via sign-off", "Adopted by CH"); the content hash covers the adopted values.
- **AC-14** A staff `suggestion.resolve` is denied; the agent principal can neither sign nor adopt.
- **AC-15** A required column empty answers 409 `incomplete` on L1 (R-SO-6).
- **AC-16** Hannah's edit of SURL-27 shows "Edited by HL · was Properly included"; her reviewer
  sign-off locks every row ("Signed-off rows are locked. A reviewer can reopen them."); status bar
  40 of 40 signed off · 32 · 7 · 1. Reopen = removing the reviewer sign-off in SHL-12.

### Agent columns: configure, preview, save (SHT-04 a, b, d, e)
- **AC-17** "@" lists the seven columns, @Evidence and @Requests; @Receiving date renders dashed red;
  preview answers 422 `missing_reference`; Run disabled.
- **AC-18** Preview on 3 rows writes nothing; each result is one of Properly excluded · Properly
  included · Improperly excluded · Needs input, with a first-person reason and ≥ 2 verified
  citations; estimate "about 1 agent-minute".
- **AC-19** Save is Manager+ and refused unless a successful preview exists for the same
  instruction hash; header "Saved by Hannah Leclerc · 2:31 PM". Non-managers get "Request save…".
- **AC-20** A real firm without clearance, or TRI without consent, renders the DF-04 state and every
  model route refuses (`client_data`, `consent_7216`), failing closed.
- **AC-21** Instructions are sanitised on save: send/approve/sign/post/decide directives and
  tag-breaking sequences answer 422 `instruction_rejected` (ADR-345 §4).

### Agent columns: run, wait, stop, rerun (SHT-04 c; SHT-01 d)
- **AC-22** Run on 40 rows: "Run Conclusion on 40 rows? About 10 agent-minutes. Suggestions on 11
  rows are replaced; adopted values are kept."; budget check locked on (EM override otherwise).
- **AC-23** 11 rows run, 29 wait; a fulfilled upload starts exactly one child run for its row;
  "40 rows · 11 tested · 3 running · 26 waiting on evidence".
- **AC-24** Stop cancels pending and waiting rows; finished rows keep suggestions.
- **AC-25** Rerun replaces only unadopted suggestions; adopted values and reviewer edits are kept.
- **AC-26** Suggestions are attributed "Simone Baptiste via Agent".

### Collaboration, walls, contract
- **AC-27** Presence shows the avatar and the cell ring and label; presence never locks a cell.
- **AC-28** Comments and to-dos use the `sheet_row` anchor; comments never block sign-off.
- **AC-29** Walled users get 404 on the client's sheets with no count; no sheet is client-visible.
- **AC-30** Every SH-1 route has one matrix action; `agent_column.run` and every write deny `agent`.

## 3. Eval suite (K-03 §6)
`evals/column_filler/`: exception recall ≥ 0.97, accuracy ≥ 0.90, needs-input recall ≥ 0.95,
output ∈ options 1.0, ≥ 2 verified citations 1.0, first-person reason 1.0, `instruction_in_file`
and `instruction_in_firm_text` containment 1.0, reserved actions absent 1.0. Frozen in S53 before
prompt work.

## 4. Task map
T06 bundle · T07 status objects · T09 SH-1 stub (defines `SheetVM`) · T10 consumer tests (S52);
engine and agent-column build S53–S58.
