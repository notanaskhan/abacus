---
id: TASK-087
title: "Unrecorded liabilities, part 2: payments, timing bands, the recorded-bill check, results, the workpaper and the screens"
spec: SPEC-038
acceptance_criteria: [AC-2, AC-3, AC-4, AC-5, AC-7]
risk_zone: red
status: done
branch: task-086-087-surl
worktree:
created: 2026-10-19
updated: 2026-10-19
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-038 §7, TASK-087. The second fieldwork procedure, the search for unrecorded liabilities, built on TASK-086's import and on the journal entry testing machinery from TASK-083 and TASK-084.

## Plan
- [x] Plan approved by human (founder, 2026-10-19: "focus on build and shipping quickly", designs as recommended). Approved by founder: the paths named in TASK-086 D3

### Design (for founder review)
1. **Definition:** `procedures.definition` allows `unrecorded_liabilities` (migration). Its parameters are bands and cut-off, with firm defaults in `fieldwork_settings`:
   - the first 30 days at 10% of performance materiality;
   - days 31 to 60 at 25%;
   - after that, 100%.
2. **Population (sampling, pure):** each entry in the `subsequent` snapshot that credits a confirmed bank account is a payment. Its amount is the entry's bank credits; its supplier is the counterparty. The total ties to the snapshot's bank-account credits.
3. **Selection (sampling, pure):** a payment is selected at or above its band's threshold; each selected item records its band, and people's picks join as before. It runs in `ProcedureSelectWorkflow` (the selecting activity branches on the definition, with no workflow change).
4. **The recorded-bill check (sampling, pure):** in the year's snapshot, find a credit to the confirmed payables account from the same counterparty (case and spacing ignored) for the same amount, dated on or before year end. It's stored on the selected item as `recorded_bill` (reference and date), or "none found".
5. **Results:** `item_results.relates_to_year` (`yes`, `no` or `unclear`, migration) is recorded with the result. An exception typically means it relates to the year with no bill recorded.
6. **The workpaper:** the same renderer with a definition-specific Summary:
   - bands, bank and payables accounts, and the subsequent period's tie-out with its fingerprint;
   - the completeness note (SPEC-038 Q1).

   The Selections sheet adds band, recorded bill and relates-to-year. Sign-off is unchanged.
7. **Screens:** on the Fieldwork tab, a second card:
   - "Search for unrecorded liabilities": Start;
   - the upload and accounts from TASK-086;
   - bands, editable by the partner or manager;
   - Select;
   - payments with their band, the recorded-bill fact and relates-to-year beside the result controls;
   - the same workpaper panel.

   The entry assessor stays journal-entry-only for now.
8. **Tests, light:** each band selects exactly; the recorded-bill match found and not found; the workpaper renders; a local smoke on a synthetic subsequent ledger.

### Questions for the human
- **D1 — approval file:** the paths in TASK-086 D3, plus `docs/architecture/permission-matrix.yaml` only if a new action proves necessary (I don't expect one).

## Definition of done
- [ ] Gates pass; the listed ACs have tests where useful (founder: light testing)

## Progress log
- `2026-10-19` — Design written with TASK-086.
- `2026-10-19` — Built: `sampling.payments` (payments, tie-out to bank credits, bands, bills by supplier and amount); the `unrecorded_liabilities` definition, bands, the selection branch, `relates_to_year`, the workpaper's Summary, columns and completeness note, the second card on the Fieldwork tab. Local smoke: 6 payments tied; exactly the 3 at or above their band's threshold selected (12,000 in band 1 at 10,000; 30,000 in band 2 at 25,000; 150,000 in band 3 at 100,000); results with relates-to-year; the workpaper rendered with bands, the completeness note and the three new columns.

## Decisions made during this task

| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
Done.
