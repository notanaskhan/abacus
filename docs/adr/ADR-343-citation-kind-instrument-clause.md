---
id: ADR-343
title: Citation v2 amendment - instrument_clause as the eleventh citation kind, ids, regions and a quote hash only, verified from the sealed layer, moved on a superseding instrument
status: accepted
date: 2026-11-14
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Number.** This is the P-48 amendment the T-07 epic calls the "clause citation kind" (catalogue row; no chapter-09 row of its own). It amends ADR-166 (P-48) §2, which says "adding an eleventh kind needs a new ADR". ADR-166 stays accepted and binding; this ADR supersedes only its kind count and adds one kind. Drafted for T-07-T02 (TASK-7934, DEC-4929).

**Status.** Accepted under the solo amendment (`docs/plan/AMENDMENT-solo.md` items 2 and 7): the builder decided with the plan's proposed option (T-07 §11.2 OQ-1, "Eleventh kind"). The plan's two-founder week-2 review and the S44 Contract Monday acceptance (Mon Jun 26, 2028) are replaced by this acceptance. T-07-T11 may merge once this file is on `origin/main` with `status: accepted`.

## Context
T-07 (trusts and estates) shows a trust's governing instrument beside seven tax determinations on TXT-01, and each determination must cite the clause it rests on (INV-2). A clause is not a page region: it is a numbered unit of a legal document ("Art. III(a)") that can span pages, and whose identity must survive re-reading the same instrument. When the trust is amended or restated, a new instrument version supersedes the old one and every determination resting on an old clause must say "Source moved".

ADR-166 fixed ten kinds. The nearest one, `document_text {evidence_version_id, page, bbox?}`, cites a page region, not a clause:
- a clause spanning pages 3–4 would need two citations and lose its label;
- re-segmentation (a person correcting the clause marking, T-07 OQ-3) would leave the citation pointing at a box rather than the clause the person chose;
- the display title would be "Page 3", not "Art. III(a)".

Constraints carried over unchanged from ADR-166: the quote is Restricted client text and is never stored (§4); evidence is immutable (ADR-004); relink is a human act (§7); display is rendered by code (§5).

## Decision
1. **An eleventh kind, `instrument_clause`.** It joins the Postgres enum `citation_kind` and `CitationKind` in `evidence/citations/registry.py` through a CHECK-widening migration (T-07-T11). Its source is `("instrument_segmentation", "segmentation_id")`. The owner module (`tax`, T-07) registers its verifier and display through `evidence.register_citable("instrument_clause", verifier, display)` from `tax/api.py`, as chapter 03 §2.4 anticipates ("tax (… instrument clauses)"). Until it registers, `instrument_clause` citations are stored unverified with `locator_invalid` (ADR-166 §2).

2. **Locator: ids only.** `instrument_clause {instrument_id, segmentation_id, clause_id, quote_sha256}`:
   - `instrument_id`: the trust instrument record (the governing document's evidence version as `tax` records it for the trust; T-07-T11 names the column);
   - `segmentation_id`: the code segmentation run that produced the clause list for that version;
   - `clause_id`: a row of `instrument_clauses` (label, heading, ordinal, page span, `regions jsonb` of `[{page, bbox}]`, `text_sha256`);
   - `quote_sha256`: the SHA-256 of the words the quote resolved to inside the clause's regions.

   The kind **stores no instrument text**: not on the citation, not on the locator, not on `instrument_clauses` (which keeps ids, regions and `text_sha256` only). The `match_id` is server-derived: `ic:<segmentation_id>#<clause_id>`.

3. **Verifier contract.** The verifier, run inside the writer's unit of work (ADR-166 §3):
   - authorises the acting principal to read the instrument's evidence version on the anchor's engagement (404, never an oracle);
   - resolves the clause in the named segmentation (`source_not_found` if the instrument, segmentation or clause is missing; `locator_invalid` if the clause does not belong to that segmentation or the segmentation to that instrument);
   - re-reads the words inside the clause's regions from the **sealed** word layer of the instrument's evidence version (the `text_layer` the P-11 epic produces), using the `document_text` quote-hash method over the clause regions in order;
   - returns `verified` when the quote's hash is found inside those regions, else `quote_not_found` (`bbox_mismatch` when the quote is found only outside them).

   It never stores, logs or returns the quote. Display re-reads the quote from the masked layer, as for `document_text` (`quote_state` shown / withheld).

4. **Display.** The display function renders `title` from the clause's code-held label and heading, for example `Art. III(a)` with `loc` "Trust agreement · pages 3–4", never from model text (INV-2, ADR-166 §5). The SHL-07 popover lights the clause's regions in the lavender passage highlight.

5. **Moved on a superseding instrument version.** When a new evidence version supersedes the instrument (an amendment or restatement), the existing `evidence_version.created` consumer writes `citation_events(kind=moved)` for every `instrument_clause` citation of the replaced version, as for `document_text` (ADR-166 §6). Re-segmenting the **same** version is not a move: the old segmentation stays readable and its citations stay `valid`; a person who re-marks clauses relinks through `POST /v1/citations/{id}/relink` (human only, ADR-166 §7), whose search runs over the new segmentation's clauses.

6. **Nothing else changes.** Verify before display, insert-only `citations` and `citation_events`, the human-only relink CHECK, the reserved `annotation_id` slot and number provenance stand as ADR-166 wrote them. A twelfth kind still needs a new ADR.

## Options considered
### Option A: an eleventh kind, `instrument_clause` — chosen
- Pros:
  - Clause identity survives re-segmentation and page breaks.
  - The display title is the clause label people read on TXT-01.
  - The verifier reuses `document_text`'s quote-hash method, so there is no new matching code path.
  - `moved` follows instrument supersession through the existing consumer.
- Cons:
  - A CHECK-widening migration on the `citation_kind` enum (red `evidence`).
  - One more verifier to keep in the citation eval suite.

### Option B: `document_text` with a clause label
- Pros: no enum change; the verifier exists.
- Cons:
  - A multi-page clause needs several citations and loses its single label.
  - The label would have to live in the locator as text the server did not derive, or be guessed from the box.
  - Re-segmentation leaves the citation on a box, not on the clause the person chose.
- Why rejected: TXT-01's determinations cite clauses, and INV-2 needs the display title rendered by code from a clause record.

### Option C: a `tax`-owned clause table cited as `record_field`
- Pros: no enum change.
- Cons: `record_field` verifies a value on a record, not a quote inside regions of a document; the quote would be unverified or need a second matching path.
- Why rejected: it hides a document citation behind a record kind and weakens verify-before-display.

## Consequences
**Positive**
- Every TXT-01 determination cites a clause by id, verified by code from the sealed layer, with a code-rendered "Art. III(a)" title.
- Amendments and restatements surface as "Source moved" on every affected determination.

**Negative / costs accepted**
- Red work in `evidence` (enum widening, verifier wiring) before T-07's determinations can be cited (T-07-T11).
- Display of a clause spanning several pages reads several regions of the layer.

**Follow-up work created**
- Code: T-07-T05 (contract stub for clause citations in C4 consumers), T-07-T11 (migration widening `citation_kind`, `instrument_clauses`, verifier, display, clause regions, `moved` on supersession), T-07-T12 (determinations cite clauses).
- Contract: `docs/contracts/c04-citations-viewer.md` gains `instrument_clause` in its kind table (additive, T-07-T11).
- Tests: T-07-T06 consumer tests (C4 `instrument_clause` kind and clause regions); `evals/citations/suite.yaml` gains fabricated-clause, wrong-segmentation and quote-outside-clause cases.
- Glossary: `instrument_clause`, `instrument segmentation`.

## Enforcement
- [ ] Lint rule: none; the rules sit in the schema and the service.
- [x] Architecture / dependency rule in CI: `tax` registers through `evidence.api` only (import-linter, ADR-137).
- [x] Test: T-07-T11's suite asserts no text column on `instrument_clauses`, the locator schema (ids and hash only), the four verifier outcomes, and `moved` on supersession; T-07-T06 consumes the C4 kind.
- [x] Hook or protected path: `evidence/**`, `backend/migrations/versions/*`, `evals/**`.
- [x] Reviewer agent checklist item: no instrument text persisted; the title rendered from the clause record, never from model text.

## Guidance for agents
Cite a clause only through `evidence.api.record_citations` with an `InstrumentClauseLocator` naming ids; the server computes `quote_sha256`, `verified` and `match_id`. Never copy clause text into a table, a locator, a log or a model prompt cache.

**Do**
```python
await evidence_api.record_citations(tx, run_id=run.id, citations=[
    InstrumentClauseLocator(instrument_id=inst.id, segmentation_id=seg.id, clause_id=clause.id),
])  # quote_sha256 and the verdict are computed from the sealed layer
```

**Don't**
```python
session.add(InstrumentClause(label="Art. III(a)", text=clause_text))  # no clause text is stored
```

## Revisit when
- A second legal-document family (operating agreements, partnership agreements) needs clause citations: decide whether it reuses `instrument_clause` with a document-type field.
- Code segmentation proves too weak and a model proposes structure (T-07 OQ-3).

## Related
- ADRs: ADR-166 (P-48, amended here), ADR-066, ADR-004, ADR-005, ADR-031, ADR-034, ADR-137.
- Docs: `docs/plan/epics/T-07.md` §0.1, §§3, 4 and §11.2 OQ-1; `docs/plan/03-backend-architecture.md` §2.4; `docs/contracts/c04-citations-viewer.md`.
