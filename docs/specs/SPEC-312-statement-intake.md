---
id: SPEC-312
title: "Statement intake: read every e-statement, unlock password-protected ones, then extract, reconcile and approve transactions"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-110, ADR-052, ADR-050, ADR-005, ADR-004]
related_specs: [SPEC-029, SPEC-030]
created: 2026-10-21
updated: 2026-10-21
---

## 1. Summary
A credit card or bank e-statement uploaded to a request item should be read, not answered with "can't read".

- Its transactions are extracted and reconciled by code.
- A person approves them before they feed planning, tie-outs and testing.

The work is phased. Phase 0 (TASK-323) is built. Later phases are recorded here so each later task builds against one plan.

## 2. Phase 0 acceptance criteria (TASK-323)
- **AC-1 Second reader.**
  - When pdfplumber finds no text in a PDF, or can't open it, PDFium (pypdfium2, already allowed) reads each page's text.
  - Statement fields are parsed from that text. Tables stay empty.
  - The extractor version is `v2`.
- **AC-2 No text is not a failure (amends SPEC-029 AC-3).**
  - A PDF neither reader finds text in is `not_extracted/needs_ocr`. The file is kept, the client isn't asked to re-upload, and the firm sees "no readable text yet".
  - Stored `unreadable/scanned` results keep their old wording.
- **AC-3 Unlock.**
  - `POST /v1/engagements/{id}/request-items/{item}/uploads/{version}/unlock` takes `{password}` under `evidence.upload`.
  - PDFium opens the stored file with the password in the isolated child and saves a copy without security.
  - The copy is uploaded to the same item through the ordinary path: scan, store, extract, check. It becomes a new version; the original is untouched. When staff unlock a file, the version carries the note "Password removed from the uploaded copy."
  - Responses: a wrong password gives 422 `wrong_password`; a PDF without a password gives 409 `not_locked`; other failures give 409 `unlock_failed`.
  - The password is never stored, logged, audited or echoed.
- **AC-4 Web.** Where a check reports an encrypted file, both the client upload checks and the firm checks panel show a password field and an Unlock button.

## 3. Phase 2-3 acceptance criteria (TASK-324)
- **AC-5 Read.**
  - `GET …/uploads/{version}/statement` (`evidence.read`) returns the approved transactions. If there are none, it returns a draft the server reads from the stored file in the isolated child:
    - PDF text: card and bank layouts, with section headings and CR, minus or parenthesised signs;
    - CSV: one amount column, or debit and credit columns;
    - OFX: card and bank.
  - Every amount is its effect on the statement balance.
  - It also returns the last 4 digits, period, printed balances, and code's reconciliation (opening + included lines = closing, and the difference).
  - A file without lines answers 409 `no_transactions`.
- **AC-6 Review.**
  - `POST …/statement/preview` takes decisions and returns the draft with them applied. Nothing is stored. Decisions are:
    - lines to exclude, each with a reason;
    - `flip_signs`, allowed only when a single-column export's convention was inferred;
    - the opening or closing balance, only when the file doesn't print it (`statement_balance_printed` otherwise).
  - The server never takes the lines from the client.
- **AC-7 Approve.**
  - `POST …/statement/approve` (`statement.approve`; the agent is denied) refuses an unreconciled statement (409 `statement_not_reconciled`) and a second approval of the same version (409 `statement_already_approved`).
  - It writes `statement_datasets` and `statement_transactions` (migration 0075, insert-only), and audits `statement.approved`.
  - Database CHECKs refuse a non-human approver and an unreconciled dataset.
- **AC-8 Web.**
  - The firm's item page shows a Transactions panel for uploaded versions, with:
    - kind, last 4 and period;
    - the balances (inputs where they aren't printed);
    - a Reconciled, Off n or Needs balances pill;
    - the sign-flip toggle;
    - a line table with include boxes and reasons.
  - Approve transactions is enabled only when the statement reconciles. Once approved, the panel is read-only and shows who approved it.

## 4. Later phases (each its own task)
- **Phase 1, OCR (needs an ADR, P-32, and an allowlist entry):** AWS Textract (expense and table analysis), in-region, with no model involved. `needs_ocr` files go through it. Claude vision is a fallback only for firms with AI-client-data consent.
- **Phase 2, transactions (built in TASK-324, except continuity and duplicates):**
  - insert-only `statement_extractions` (issuer, last 4 only, period, balances, payments, charges);
  - `statement_lines` (date, description, amount, side, page and box, for citations);
  - a reconciliation computed by code: opening + charges − payments and credits = closing; an unreconciled statement can't be approved;
  - CSV, OFX and QFX statement imports;
  - continuity across months, and detection of overlapping or duplicate statements.
- **Phase 3, approval (built in TASK-324; source highlight later):** a side-by-side review with the source line highlighted, line edits and exclusions with reasons, and one approval by a named person that makes an immutable transaction dataset. The agent never approves (ADR-005).
- **Phase 4, use:** approved facts go to an engagement fact store the agent may cite. Proposed risks (personal or related-party spend, round amounts, weekend spend) go to people. Also: a sampling and JE-testing population, a proposed tie-out of the closing balance against the card liability account, post-period charges for the unrecorded-liabilities search, and matching a statement to its request (period and last 4). For CAS, GL-account suggestions. The real model route is enabled here, only after a passing parity report.
- **Throughout:** card data is Restricted, only the last 4 digits are kept, and descriptions are never logged.
