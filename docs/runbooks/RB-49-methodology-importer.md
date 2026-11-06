---
id: RB-49
title: Methodology importer failures and its kill switch
owner: the builder (solo; AMENDMENT-solo)
alarms: []
last_rehearsed: never
---

# RB-49 · Methodology importer

**Module:** `agents` (`methodology_import.py`) and `methodology` · **Severity:** SEV-3 by default; a
PII hold that did not hold is SEV-1 · **Task:** K-01-T26 (TASK-5017)

`POST /v1/methodology/imports/{id}/start` hands a PDF to `MethodologyImportWorkflow`
(`methodology-import-v1`, background class). It proposes; a person reviews the flags and approves
the version in KNW-02. A firm's content arrives only through this route or the workbook import,
never a migration, constant or seed.

## The steps
1. `extract_pages` reads every page in `kernel.pdf_pages`' isolated child. An unmasked SSN, ITIN or
   EIN anywhere fails the import `pii_hold` before any model call. An encrypted or malformed file
   fails with its own code.
2. `parse_batch` runs once per eight pages through `ai_gateway` with the registered prompt, the pages
   delimited as untrusted. A cancelled import stops the loop; a budget or boundary refusal fails it.
3. `finish`: code verifies every quote on its page, sets each step's flag and writes the template's
   next version, in Needs review.

## Stop it now
Turn `methodology.importer` off for the firm. It is both the rollout flag and the kill switch: with
it off, `start` answers 409 `importer_not_enabled` for a document. It does not stop an import already
running; `POST /v1/methodology/imports/{id}/cancel` does that. The workbook path keeps working. Turning off
`methodology.import_review` also takes away upload, diff, mapping and flags in KNW-02.

## When an import fails
| Failure | What it means | What to do |
|---|---|---|
| 409 `importer_not_enabled` | The flag is off, the firm isn't synthetic and the agent isn't cleared (ADR-112), or there is no PDF (a Word file is not parsed yet) | Expected. Upload a PDF print or use the workbook path; clearance and opt-in come first |
| `pii_hold` | The document holds an unmasked SSN, ITIN or EIN | Have the firm remove it and upload again. Never relax the hold |
| An encrypted or malformed file's code | The file can't be read | Ask for an unencrypted PDF print |
| A budget or boundary refusal | The gateway refused the call | Check the firm's budget and ADR-112's boundary; do not route around them |
| Steps flagged | A quote didn't verify, or a step needs a person | Normal. The person resolves flags in KNW-02 before approving |

## Afterwards
Nothing to clean up in evidence: source files are write-once. A failed import writes no version. To
retry, start a new import. Record what happened under the incident's task.
