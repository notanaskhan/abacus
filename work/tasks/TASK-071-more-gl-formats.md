---
id: TASK-071
title: "General ledger detail, part 3: QuickBooks Desktop, NetSuite and Sage Intacct general ledger exports"
spec: SPEC-034
acceptance_criteria: [AC-1, AC-2, AC-3, AC-5]
risk_zone: amber
status: done
branch: task-071-more-gl-formats
worktree:
created: 2026-10-15
updated: 2026-10-15
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-034 Q1's follow-up. Clients on QuickBooks Desktop, NetSuite or Sage Intacct can upload their general ledger too, as they already can their trial balance (TASK-068). Everything after parsing is unchanged: the checks, snapshots, workbooks and fulfilment.

## Scope
SPEC-034 AC-1, AC-2, AC-3 and AC-5 for three more formats.

## Context to load
- Spec: `docs/specs/SPEC-034-general-ledger-detail.md`; TASK-068 (the trial balance formats for these systems)
- Code: `connections/gl_formats.py` (`GlFormat`), `connections/gl_parse.py` (`parse_gl_to_file`), `abacus_tools/synthetic/general_ledger.py`

## Plan
- [x] Plan approved by human (founder, 2026-10-15: D1–D2 as recommended). Approved by founder: the paths named in D2

### What the code shows
- **The parser reads one layout today:** an account heading row, an opening balance row, the postings and a total row. QuickBooks Online and Xero both export this way.
- **NetSuite and Sage Intacct general ledger exports are usually flat:** every line carries its account in a column, with no heading rows. Sage Intacct also puts the code in its own column, as its trial balance does.
- **The format list and steps come from the API,** so the screen needs no change.

### Design (for founder review)
1. **Three formats** (configuration, D1), from each system's documented general ledger export:

   | Format | File | Layout | Account | Amounts | Opening | Total |
   |---|---|---|---|---|---|---|
   | QuickBooks Desktop (`qbd_gl_xlsx`) | Excel | headings | "1000 · Checking" | Debit / Credit | "Beginning Balance" row (Balance column) | "Total 1000 · Checking" |
   | NetSuite (`netsuite_gl_csv`) | CSV | flat | "Account" column, "1000 - Checking" | Debit / Credit | rows typed "Opening Balance" | none (summed) |
   | Sage Intacct (`intacct_gl_csv`) | CSV | flat | "Account no." and "Account title" columns | Debit / Credit | rows described "Beginning balance" | none |

2. **The parser gains a `flat` layout:** each line's account comes from its own column, either one heading text with a leading code or separate code and title columns. Opening balance rows are recognised by their type or description column. QuickBooks Desktop fits the existing heading layout, with the " · " separator, which is already handled.
3. **Telling formats apart:** a file from one system uploaded under another is refused as `unrecognised_format`, as today. Each format's required headers differ from the others', and a test covers every pair.
4. **Synthetic fixtures:** writers for the three layouts, built from the same synthetic ledgers, so they reconcile by construction and carry the same six flaws.
5. **Tests:**
   - each format reconciles across several generated trial balances;
   - each flaw fails its own check in each format;
   - wrong-system files are refused;
   - a local smoke uploading each format through the worker, with both requests filled.

### Questions for the human
- **D1 — layouts without real samples:** as with TASK-068, I recommend building from the documented layouts and synthetic fixtures. Any real anonymised export that doesn't read becomes a quick configuration fix.
- **D2 — approval file:** `backend/src/abacus/modules/connections/**`, `backend/tests/unit/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-15` — Design written for founder review after SPEC-034 completed (#124).
- `2026-10-15` — Built (D1–D2): three formats; the parser's `flat` layout; synthetic writers. Unit and workflow tests (10,566; the GL suite now 86: five generated trial balances in all five formats reconcile, each flaw fails its own check in each, every wrong-system pair is refused) and gates pass. Local smoke through the worker: each new format reconciled after the trial balance arrived and filled the general ledger and journal requests; the same file again was recognised.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
Done. When anonymised real exports are shared, run each through `parse_gl_to_file` and adjust its format's configuration if needed.
