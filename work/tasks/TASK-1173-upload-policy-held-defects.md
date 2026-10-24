---
id: TASK-1173
title: The upload policy - 50 MB, the type allowlist by bytes and name, active-content PDFs, HEIC (Q-03-T016 upload part; ED-018 to ED-021)
spec: SPEC-020
acceptance_criteria: [AC-9]
risk_zone: red
status: done
epic: Q-03
plan_key: Q-03-T016
branch: s7c-client-uploads
created: 2026-10-24
updated: 2026-10-24
---

## Objective
Fix the held upload defects ED-018, ED-019, ED-020 and ED-021 so their strict xfails become passing tests, under the upload policy Ayush decided on 2026-10-24 (DEC-296, citing DEC-58 c).

## Plan (red zone)
- **Code:** `evidence/uploads.py` (50 MB; `sniff` recognises HEIC/HEIF, TIFF, GIF, macro-enabled OOXML; text is CSV only when it parses; `allowed_type` checks the allowlist and the extension; scan first; `Screened` carries the active-content reason); new `evidence/active_content.py` (pure token scan); `extraction.py`, `previews.py`, `words.py` never read an active PDF; `checks.py` firm `active_content` check; `viewer.py` 409 `active_content`; `inbox.py`, `setup_files.py` pass the file name; `api/middleware.py` route-scoped edge limit, wired in `api/app.py`.
- **Migrations, flags, matrix:** none.
- **Tests:** remove the five strict xfails in `tests/security/test_upload_hostile_files.py`; `tests/unit/evidence/test_upload_policy.py` (new); the back-fill `test_client_uploads_and_processing.py` follows the policy where DEC-296 says.
- **Rollback:** revert the commit; no data changes.

## Progress log
- 2026-10-24: built. Kept `sniff` recognising OLE (the SPEC-020 unit test pins it) and moved the refusal to `allowed_type`. EICAR in a file named `.pdf` is text, not CSV: the scan now runs before the type check so it still answers `file_refused` (the hostile suite's assertion). Changed test inputs only per DEC-296: the back-fill's oversize body (50 MB + 1) and its XLSX upload's name. The legacy type message in the web app still lists six types (`spec020.test.tsx` pins it); its size line now says 50 MB.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-296 | The upload policy of 2026-10-24 (DEC-58 c) | No |
