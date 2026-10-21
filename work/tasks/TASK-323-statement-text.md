---
id: TASK-323
title: "Statement intake phase 0: PDFium text fallback, needs_ocr instead of a failure, and unlocking password-protected PDFs"
spec: SPEC-312
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4]
risk_zone: red
status: done
branch: task-323-pdf-text
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan
- **`evidence/extraction.py`:** `_pdfium_pages` and `_fallback`; no text gives `not_extracted/needs_ocr`; `EXTRACTOR_VERSION` is v2.
- **`evidence/unlock.py`:** `remove_password` (isolated; returns an outcome rather than raising across processes) and `unlock_upload`, which re-uses `upload()`.
- **Route:** `…/uploads/{version}/unlock`; the body's `SecretStr` password is classified restricted.
- **Web:** `UnlockForm` in `CheckResults.tsx`; new wording in `checkMessages.ts` for encrypted and needs_ocr.
- **Fixture:** `tests/unit/evidence/fixtures/locked_statement.pdf`, a synthetic statement encrypted with AES-256 by qpdf. Its password is in the test.
- No migration, no new dependency. Rollback is a revert.

## Notes
- This amends SPEC-029 AC-3: a scanned PDF is no longer a client problem. The test was updated to the amended criterion.

## Definition of done
- [x] `tests/unit/evidence` (177) and the app gates pass.
- [x] spec029checks and spec029preview (24) pass.
- [x] check-fast passes.
