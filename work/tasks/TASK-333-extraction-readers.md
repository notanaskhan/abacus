---
id: TASK-333
title: "Fix: earlier uploads' previews read as empty after the extractor version bump"
spec: SPEC-312
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
branch: task-333-extraction-readers
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Root cause
TASK-323 bumped `EXTRACTOR_VERSION` from v1 to v2, but every reader looked an extraction up by the current version only. Uploads extracted by v1 therefore had "no extraction", so the spreadsheet preview showed "This spreadsheet is empty".

The same lookup also hid earlier extractions from:
- the client view's account digits;
- inbox matching and the inbox list;
- the checks step;
- the agent's review material.

## Fix
- `repository.newest_extraction`: an upload's newest extraction by any version. Every reader uses it.
- Upload processing still records one extraction per version (`extraction_for` with the version).
- `tests/unit/evidence/test_extraction_readers.py` fails if any module other than `processing.py` looks extractions up by version.

## Progress log
- Found from the founder's screenshot: the item page showed "This spreadsheet is empty" while screening cited C9 and D9.
- Verified on dev data: a v1-extracted workbook now previews its two sheets (Journals, 109 rows; About, 14).

## Definition of done
- [x] `tests/unit/evidence` (175) passes.
- [x] check-fast passes.
