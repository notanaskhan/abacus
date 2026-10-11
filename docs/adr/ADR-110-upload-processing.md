---
id: ADR-110
title: Uploads are scanned, then parsed in isolation; extraction never alters evidence
status: accepted
date: 2026-10-11
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Client uploads are hostile content (ADR-052). Checking them (mechanical checks, previews, later the upload reviewer) needs their text and tables.

## Decision
- **Malware scan before any parsing.** A scanner interface; locally a stub that rejects known test signatures; the real scanner is chosen with staging (TASK-014). A file that isn't scanned clean is never parsed or previewed.
- **Parsing runs in an isolated worker**, as Temporal workflows (ADR-017, ADR-090), with time, memory, size and page limits.
- **Spreadsheets:** formulas are never evaluated (cached values only); macros are ignored; archive bombs are rejected.
- **Scanned PDFs (no text layer):** reported as unreadable, with guidance to upload the bank's digital statement, until an OCR service is chosen with staging.
- **Extracted text and tables are a derived record** linked to the evidence version. They never alter the evidence, and they can be rebuilt.
- **Previews** are server-made page images (PDF) and extracted cached values (spreadsheets); the browser never renders the raw file.

## Options considered
### Scan, isolate, derive — chosen
- Pros: hostile files never reach a parser unscanned or the browser unrendered
- Cons: a scanner and an isolated worker to run

### Parse in the API process
- Pros: simple
- Cons: one malicious file can take down or compromise the API
- Rejected.

## Related
ADR-004, ADR-016, ADR-017, ADR-052, ADR-090, ADR-111.
