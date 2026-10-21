---
id: SPEC-308
title: "Working papers, first slice: the grid, formulas computed by code, tickmarks, cell citations, and L1–L5 sign-offs with staleness"
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-004, ADR-050, ADR-005, ADR-136, ADR-140]
related_specs: [SPEC-037, SPEC-300]
created: 2026-10-21
updated: 2026-10-21
---

## 1. Summary
This is the first slice of the audit core's working papers (A-04). It also adds the review grammar's first engine, sign-offs (P-04).

- A paper belongs to the engagement's assurance work item and has a reference unique on the engagement (`C-100`).
- Its grid is insert-only: an edit appends a cell row, and the newest row is the value.
- Code computes formulas (ADR-050).
- Cells carry tickmarks, and can cite evidence versions the engagement holds.
- Sign-offs come from the new `review` module. Each records the content hash it approved and saves a numbered version. A later change shows the sign-off as stale; it is never deleted.

The existing procedure workpaper tables (SPEC-037) are renamed to `procedure_workpaper_*`. Migration 0072 does the rename.

## 2. Acceptance criteria
- **AC-1 Index.**
  - `GET /v1/engagements/{id}/workpapers` lists papers by reference, through `visible()`.
  - Each paper shows its status, in `audit_section` registry codes: not_started · in_progress · prepared · reviewed · signed_off · changed_after_signoff.
  - Each paper shows its five levels and its cell and citation counts.
- **AC-2 Create.**
  - `POST` takes a reference matching `^[A-Z0-9][A-Z0-9.-]{0,19}$`, a title and an optional area.
  - A second paper with the same reference on the engagement gets 409 `workpaper_code_taken`.
  - An engagement without an assurance item gets 409 `no_assurance_item`.
- **AC-3 Grid.**
  - `PUT …/{wp}/cells` takes up to 200 edits of cell key, raw text (2,000 characters at most) and tickmarks from a fixed set. Unchanged cells write nothing.
  - Raw text starting with `=` is a formula:
    - decimal `+ - * /`, unary minus, parentheses, references, and `SUM(A1:B9)`;
    - errors are values: `#REF!`, `#CYCLE!`, `#DIV/0!`, `#ERR!`;
    - numbers typed as `1,250.00`, `(400)` or `$12` parse;
    - no floats anywhere.
- **AC-4 Citations.** `POST …/{wp}/cells/{cell}/citations` cites an evidence version. A version from another engagement answers 404.
- **AC-5 Sign-offs.**
  - The routes are `POST …/{wp}/sign-offs/{prepare|review|manager|partner|eqr}`, one matrix action each:
    - L1: staff, senior or manager;
    - L2: senior, manager or EP;
    - L3: manager or EP;
    - L4: EP;
    - L5: the EQR (`reviewer`).
  - The agent is denied every level.
  - L2 and above need a current L1 (409 `not_prepared`).
  - The L1 signer can't sign L2 (409 `preparer_cannot_review`).
  - Re-signing the same content at the same level is refused (409 `already_signed`).
  - The content hash is sha256 over the filled cells (raw text and tickmarks) and the citations.
  - Each sign-off writes a `workpaper_versions` row holding that content.
- **AC-6 Web.**
  - A "Working papers" engagement tab holds the index (status pill, sign-off squares, New working paper).
  - The paper page has:
    - the A–H grid, with keyboard movement and typing to edit;
    - a formula bar and a tickmark menu;
    - a "Cite source" sheet;
    - the sign-off rail (stale levels struck, "Sign again");
    - the version list.

## 3. Out of scope (later slices)
- Multiple sheets (`workpaper_sections` exists for this).
- Trial-balance-linked cells (A-02 and A-03).
- Agent-proposed values.
- Review notes on cells.
- Opening a citation in the source viewer, which needs the request item on the evidence version listing.
- Export.
