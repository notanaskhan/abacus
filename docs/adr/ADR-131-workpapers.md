---
id: ADR-131
title: A workpaper is rendered by code, versioned, and signed off by people; it never changes once reviewed
status: accepted
date: 2026-10-19
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, **stop** and raise it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Fieldwork (SPEC-037) makes Abacus hold audit documentation, not only evidence. Audit standards expect documentation that an experienced auditor with no previous connection to the audit can understand (AU-C 230, AS 1215). It must show who prepared and who reviewed each piece and when, and it can't be changed after the documentation completion date except by recorded additions. A workpaper an agent writes freely, or one that can be edited after sign-off, fails that.

## Decision
1. **A workpaper is a record with versions, never edited in place** (as evidence is, ADR-004). Each version holds:
   - the procedure and engagement it documents, and its inputs by reference: snapshots, populations, selections and evidence versions;
   - its rendered file (XLSX), produced by code from those inputs, deterministically (ADR-042): the same inputs always give the same bytes;
   - the person and agent contributions it includes, each attributed.
2. **States:** `draft` → `ready` (the preparer signs) → `reviewed` (a reviewer who isn't the preparer signs). Each signature is a record with who, when and the version signed. Changing anything makes a new `draft` version, and the signatures stay on the old one.
3. **Model-written text** (rationales, summaries) appears in a workpaper only as an attributed, AI-tagged section that a person approved (ADR-005, ADR-065). Code writes every figure, total and selection (ADR-050).
4. **Locking:** when the engagement's documentation is complete (a later spec sets the date rule, Q1), its workpapers are locked. Afterwards, only an addendum version with a reason is allowed, never a replacement.
5. **Workpapers are firm-only.** Clients never see them (ADR-111).

## Options considered
### Option A: versioned records, rendered by code, signed by people — chosen
- Pros: meets documentation and review standards; reproducible; fits ADR-004 and ADR-042.
- Cons: no free-form editing inside the platform; a change is a new version.

### Option B: an editable spreadsheet in the app, as some products show
- Pros: familiar; flexible.
- Cons: figures can drift from the data; hard to prove what was reviewed; agents could write numbers.
- Why rejected: fails ADR-050 and the review trail.

## Consequences
**Positive**
- Every figure traces to a snapshot and a rule; every signature to a version.

**Negative / costs accepted**
- Preparers annotate through structured fields and notes, not cell edits. A download is a copy, not the record.

**Follow-up work created**
- SPEC-037 (procedures and workpapers); a later spec for documentation completion and locking.

## Enforcement
- [ ] Test: rendering is byte-identical for the same inputs.
- [ ] Test: a reviewer can't be the preparer; a signed version can't change.
- [ ] Schema: workpaper versions and signatures are insert-only (schema_check).

## Guidance for agents
Agents may propose per-item assessments and draft narrative for a workpaper. They never write figures, choose samples or sign.

## Revisit when
- A firm needs workpapers in its own existing documentation system (export formats).
- PCAOB (issuer) audits come into scope (AS 1215's stricter timelines).

## Related
- ADRs: ADR-004, ADR-005, ADR-042, ADR-050, ADR-065, ADR-111, ADR-132.
- Specs: SPEC-034, SPEC-037.

## Open questions (resolved before acceptance)
All resolved: the founder approved every recommendation below on 2026-10-19.
- **Q1: documentation completion.** *Recommendation:* out of scope for SPEC-037. A later spec adds the date (60 days after the report release date for non-issuer audits, AU-C 230) and the lock. Until then, `reviewed` versions are immutable but an engagement isn't locked.
- **Q2: reviewer roles.** *Recommendation:* the preparer is staff, senior or manager; the reviewer is a senior, manager or partner who isn't the preparer, as the firm's methodology usually requires. Firm-configurable levels come later.
