---
id: ADR-400
title: "Document-extracted ledger snapshots and GL journal-entry fields"
status: proposed
date: 2026-10-30
deciders: notanaskhan, ayushkbhatia
risk_zone: red
proposal: P-58
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

Drafted with A-05-T03 (TASK-2605) from DEC-82. The plan's alias for this ADR is "ADR-155", which
P-03 (the design system) took first; ADR numbers are never reused, so P-58 is ADR-400. Acceptance is
due by **Fri Sep 3, 2027** (S22), before A-04-T08 reads a document-extracted trial balance and
before any ledger code from A-05-T28 or A-08-T09 merges. Red: it changes the protected ledger model
(`ledger_snapshots`, `gl_entries`) and the protected GL parsers (`connections/gl_formats.py`,
`connections/general_ledger.py`), so both founders accept it and it never defaults on silence
(chapter 09 §9.0).

## Context

Two gaps in the ledger model block audit work on real engagements.

1. **A trial balance that only exists on paper.** An employee benefit plan's investments are held
   by a trustee or custodian; the plan's trial balance is built from the certified trust report, a
   PDF (EBP-06; A-05 §3; DEC-82). Today a `ledger_snapshots` row comes only from a connector pull or
   one of the SPEC-028 import formats (`source_kind` `import`, `fake`, `other`; migration 0149). There
   is no way to say "these figures were read from this document" and no rule for how such a snapshot
   may be made. Without one, the agent path either cannot build the plan TB at all, or builds it
   with nothing on the row to tell a reviewer that it came from a document rather than a ledger.
2. **Journal-entry testing without journal-entry facts.** AU-C 240 journal-entry testing (AUD-12)
   reads who posted an entry, when it was entered, whether it was manual or system-generated, and
   who approved it. `gl_entries` (0051) carries none of these, although several GL export formats
   do. Without columns for them the criteria cannot run, and nothing distinguishes "the ledger did
   not export this" from "the entry has no approver".

Constraints: ledger snapshots and GL rows are immutable (ADR-004); code computes and models judge
(ADR-050); an agent never adopts a trial balance of record (ADR-005; A-02's human-only
`trial_balance_versions`); every citation is verified (C4; INV-2); client content is hostile
(ADR-052); `source` is free text and `source_kind` is generated from it by an explicit list that may
only change after proving no stored row's kind moves (0149, DEC-316).

## Decision

**1. A document-extracted snapshot is a ledger snapshot with its document named.**
`ledger_snapshots.source = 'document_extraction'` marks a trial balance read from a document. The
table gains `source_evidence_version_id uuid NULL` (the evidence version the figures were read
from) and `extraction_run_id uuid NULL` (the agent run that proposed them, when one did), with
`CHECK (source <> 'document_extraction' OR source_evidence_version_id IS NOT NULL)`. The generated
`source_kind` gains `document` for that source, through the 0149 rule: the migration first proves
over every stored row that no other row's kind changes, and refuses to run if any would. Expand
only: existing rows are untouched and no immutable row is updated.

**2. Only `ledger.api.record_document_snapshot` writes one, and only from verified, footing lines.**
It takes the document's lines (account, debit, credit) each with its citation, and the totals the
document states. In code, before anything is stored, it:
- verifies every line's citation through C4 (the evidence version, page and region exist and the
  cited text holds the figure); one unverified line refuses the whole snapshot (422
  `citation_unverified`);
- foots the lines (debits = credits, the existing `ledger_snapshots_balanced` CHECK) and ties
  them to every total the document states (fund by fund and for each date it reports, for a trust
  report); any difference refuses the snapshot (422 `footing_difference`, naming the total);
- stores the snapshot and its lines in one unit of work with its audit event, its provenance
  columns filled, immutable from then on.
An agent may propose the lines and run the extraction; the arithmetic, the tie and the decision to
store are code's (ADR-050).

**3. Adoption stays a person's.** A document-extracted snapshot becomes the trial balance of
record only through A-02's human-only `trial_balance_versions` path, like any other snapshot
(ADR-005). No agent context, schedule or system principal adopts one.

**4. Provenance is shown, never hidden.** Wherever a trial balance of record is shown (AUD-06,
EBP-06, the TB label chip), a document-extracted snapshot reads "Document extraction" with a link
to its source document, distinct from an import or a connector pull. Readers of the ledger
(`ledger.api`) return the provenance with the snapshot.

**5. GL journal-entry fields are recorded where the export carries them, and only there.**
`gl_entries` gains four nullable columns: `posted_by` (the ledger's user as exported, text),
`entered_at` (timestamptz), `source` (`manual` or `system`) and `approver` (text). `gl_snapshots`
gains `je_fields_available` (the subset the import's format carried). The column maps live in
`connections/gl_formats.py`, per format, for the formats whose exports carry them; a format that does
not carry a field leaves it NULL and says so in `je_fields_available`. Existing snapshots report the
fields as unavailable. A journal-entry criterion that needs a field the snapshot lacks shows "Not
available from this ledger" and is never inferred, estimated or filled by a model. `posted_by` and
`approver` are classified `confidential` (people's names from a client system) and never logged.

**6. Both halves are expand-only and land behind accepted status.** A-05-T28 (the snapshot half,
S26) and A-08-T09 (the GL half) each ship one expand-only migration, and neither merges before this
ADR is accepted on `main`.

## Options considered

### Option A: a ledger snapshot with document provenance, written only by a verifying API — chosen
- Pros: every existing reader of trial balances (layers, leadsheets, mapping, AUD-06) works
  unchanged; provenance is on the row and enforced by a CHECK; the immutability and adoption rules
  are the ones already proven; the agent path and the template-import path both end in the same
  human adoption (A-05 OQ-2: they complement each other).
- Cons: a new value in `source_kind`'s generated expression, which needs the 0149 proof migration;
  one more red API in `ledger`.

### Option B: treat the trust report as a filled-in TB template import
- Pros: no ledger change; the A-02 template import already exists.
- Cons: the snapshot would claim to be an import with no link to the document it came from; the
  citations and the tie to the stated totals would live nowhere enforceable.
- Why rejected: it hides provenance from the reviewer, which DEC-82 requires to be "recorded as
  different". It remains the agent-off path.

### Option C: let the agent write the trial balance straight from the document
- Pros: fastest to build.
- Cons: a model would be doing the arithmetic and choosing what to store; no code tie.
- Why rejected: contradicts ADR-050 (code computes) and ADR-005 (agents propose, humans decide).

### Option D: a separate `document_trial_balances` table
- Pros: no change to `ledger_snapshots`.
- Cons: every TB reader would need a second source; two immutability and adoption paths.
- Why rejected: duplicates the ledger for one provenance difference.

### Option E (GL half): derive JE facts from descriptions or references when the export lacks them
- Why rejected: guessing who posted or approved an entry is not evidence; the criteria must say
  "Not available from this ledger" instead (DEC-82).

## Consequences

**Positive**
- EBP plan trial balances from certified trust reports become possible on the agent path, with the
  figures cited, footed and tied by code, and the provenance visible on every screen that shows them.
- AUD-12's journal-entry criteria run on the formats that carry the facts and say honestly when a
  ledger does not.

**Negative / costs accepted**
- Two red migrations (A-05-T28, A-08-T09) and the `source_kind` proof step.
- A refusal on one unverified line or one footing difference blocks the whole snapshot; the person
  fixes the extraction or falls back to the template import. This is deliberate.

**Follow-up work created**
- A-05-T28: migration and `ledger.api.record_document_snapshot`; A-05-T38 independent tests.
- A-08-T09: GL JE columns, `gl_formats.py` maps, `ledger.api.journal_entries`, availability facts.
- Glossary rows: *document extraction* (snapshot provenance); *journal-entry fields*.
- Error codes `citation_unverified` and `footing_difference` in `docs/architecture/error-codes.yaml`
  when the API lands.

## Enforcement
- [x] Database: `CHECK (source <> 'document_extraction' OR source_evidence_version_id IS NOT NULL)`;
  `ledger_snapshots_balanced`; the `ledger_immutable()` triggers (ADR-004).
- [x] Human-only: adoption through `trial_balance_versions` stays in the human-only actions register.
- [ ] Test (A-05-T38): a snapshot with one unverified line or a footing difference is refused; an
  agent principal cannot adopt one; walled users read nothing; provenance shows on AUD-06.
- [ ] Test (A-08-T09): existing snapshots report the JE fields unavailable; a format without a field
  leaves it NULL; no immutable row is updated.
- [ ] Banned pattern: only `ledger.api.record_document_snapshot` inserts a snapshot with
  `source = 'document_extraction'` (a rule like TAXAPPROVE-001, added with A-05-T28).
- [x] Protected paths: `modules/ledger/*`, `connections/gl_formats.py` and
  `connections/general_ledger.py` stay protected; changes need the red security review.

## Guidance for agents
An agent may read a trust report and propose its lines with citations. It never stores a snapshot,
never adopts one, and never computes the totals: hand the lines to `record_document_snapshot` and let
code verify, foot and tie them. For journal-entry testing, read `je_fields_available` first and
report "Not available from this ledger" for anything it lacks.

**Do**
```python
snapshot = await ledger_api.record_document_snapshot(
    ctx, entity_id, period, lines=cited_lines, stated_totals=totals, evidence_version_id=report_v
)
```

**Don't**
```python
# writing the plan TB straight from extracted text, or filling posted_by from a description
await session.execute(insert(LedgerSnapshot).values(source="document_extraction", ...))
```

## Revisit when
- A custodian or recordkeeper feed replaces the trust-report PDF for most plans.
- A second document type (a bank confirmation, a fund administrator's statement) needs its own tie
  rule.
- A GL export format starts carrying a JE fact this ADR does not name.

## Related
- ADRs: ADR-004 (immutable evidence and ledger), ADR-005 (agents propose, humans decide), ADR-037
  (connector contract), ADR-050 (code computes, models judge), ADR-052 (hostile content), ADR-340
  (sampling engine, which reads populations from these snapshots)
- Decisions: DEC-82; DEC-316 (`source_kind` from an explicit list); A-05 OQ-2 and R16
- Plan: `docs/plan/epics/A-05.md` (T03, T28, T38; M5), `docs/plan/epics/A-08.md` (T09)
- Code today: `backend/migrations/versions/0009_connections_ledger_fulfilments.py`,
  `0051_general_ledger.py`, `0149_tb_of_record_labels.py`; `connections/gl_formats.py`
