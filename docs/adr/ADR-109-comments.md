---
id: ADR-109
title: Comments are append-only, pinned to a version, and internal unless shared
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
Clients and engagement teams need to discuss requests and evidence without emailing files or losing track of which version was meant. Evidence is immutable and versioned (ADR-004).

## Decision
- **Append-only:** a comment is never edited or deleted. A mistake is fixed by a follow-up comment marked as correcting it.
- **Redaction:** a firm administrator may redact a comment posted in error (for example a password). The text is hidden and replaced by an audited stub naming who redacted it, when and why. Nothing is deleted.
- **Pinned to the exact version** it concerns: a request item, or a specific evidence version. A later version starts its own thread; earlier threads stay with the version they discuss.
- **Restricted classification** (ADR-031): comments can carry client financial information.
- **Visibility:**
  - a firm user's comment is internal by default, with an explicit "share with client";
  - a client's comment is always visible to both sides;
  - internal notes are visually distinct, so nobody mistakes what the client can see.
- Mentions notify the person mentioned; every comment and redaction is audited.

## Options considered
### Append-only with redaction — chosen
- Pros: a trustworthy record; the one real need for removal is covered
- Cons: typos stay, with a correction beside them

### Editable comments with history
- Pros: familiar
- Cons: "which wording did the client see?" becomes a question
- Rejected.

## Related
ADR-004, ADR-031, ADR-052 (comments are untrusted input to agents), ADR-110.
