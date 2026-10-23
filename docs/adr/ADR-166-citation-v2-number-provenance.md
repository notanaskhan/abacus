---
id: ADR-166
title: Citation v2 and number provenance - ten verified kinds, verify before display, no stored quote text, moved and broken computed from insert-only events, relink as a human act, a reserved annotation_id slot
status: accepted
date: 2026-10-23
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Number.** This is ADR **P-48** (chapter 09; alias AG-07). The plan text names it "ADR-144". That number was taken by P-44 (ADR-144, request status enum migration) before drafting started, so P-48 takes the next free number on `main`, ADR-166 (`docs/adr/backlog.md`; `AMENDMENT-solo.md` item 8). Read every "ADR-144" in `docs/plan/epics/P-03.md`, `P-03.tasks.csv` and `07-sprint-plan.md` that refers to citations as ADR-166.

**Status.** Accepted under the solo amendment (items 2 and 7): the builder decided with the plan's proposed option. There was no two-founder acceptance. Drafted for P-03-T27 from chapter 03 §3.7.2, chapter 05 §5.3.10 and P-03 §§3, 4.2, 4.3 and 6.

## Context
Today a citation is a page and a quote, written as JSONB on an agent output (`handoff.Citation`, ADR-054). Code verifies it before display (ADR-066). It has no region on the page, no cell or ledger kinds, and no record of the source being replaced. SHL-07 (citation popover) and SHL-08 (source viewer) need a citation that:

- opens at a lit region;
- covers spreadsheets, ledgers, workpapers, methodology, policies, records, tax forms, run artifacts and requests;
- says "Source moved" when the source is replaced.

58 inbound links and 46 referencing screens depend on that contract (C4, freeze S5).

Three constraints shape it:
1. **The quote is Restricted client text.** A second copy in a citations table would sit outside the evidence version's retention, hold and crypto-shred rules (ADR-034, P-14).
2. **Evidence is immutable** (ADR-004). A source changes only by gaining a new version, so a citation cannot be "updated" when its source moves.
3. **Agents propose, humans decide** (ADR-005). Re-pointing a citation at a new source is a judgement.

Agent prose also carries numbers. A figure the model typed is not evidence, even when it sits next to a citation.

## Decision
1. **One `citations` table in `evidence`, insert-only.** Citations are first-class rows owned by the `evidence` module. Agents write them through `evidence.api.record_citations(tx, …)` inside their handoff unit of work. No second index exists: chapter 05's `citation_index` in `agents` is not built, and P-10 reads this table. A trigger rejects UPDATE, DELETE and TRUNCATE for every role (the `evidence_versions` pattern).

2. **Ten kinds, a discriminated union on `kind`.** The ten kinds are `document_text`, `sheet_cell`, `ledger_line`, `workpaper_cell`, `methodology_step`, `policy_rule`, `record_field`, `tax_form_line`, `artifact_cell` and `request_item` (Postgres enum `citation_kind`). Each kind has:
   - a typed locator, validated per kind (chapter 05 §5.3.10). Examples: `document_text {evidence_version_id, page, bbox?, annotation_id?}`, `sheet_cell {evidence_version_id, sheet, cell, value?}`, `methodology_step {template_version_id, step_key, step_n}`;
   - a code verifier, registered through `evidence.register_citable(kind, verifier, display)`. A kind whose source module does not exist yet has no verifier, and its citations are stored unverified with `locator_invalid` until the owner registers one;
   - a server-derived `match_id`, for example `ev:<version>#p<page>:<x0>,<top>,<x1>,<bottom>`, `<file>!<cell>` or `ms:<step_key>@<ver>`.

   Adding an eleventh kind needs a new ADR.

3. **Verify before display.** Code verifies every citation when it is written (ADR-066):
   - The page, cell, line, step or record must exist.
   - The quote must appear in the source. For `document_text` that means inside the resolved bbox.
   - A cited value must equal the source value.

   A failing citation is still stored, with `verified=false` and a `verification_reason`. The reasons are `page_not_found`, `cell_not_found`, `quote_not_found`, `value_mismatch`, `bbox_mismatch`, `source_not_found`, `source_not_visible` and `locator_invalid`. A CHECK enforces `verified OR verification_reason IS NOT NULL`. Every reader shows a failed citation as "Unverified", never as fact. A change that rests only on unverified citations cannot be approved (`422 uncited_change`, ADR-160 and ADR-161). A missing bbox alone never fails a `document_text` citation: when the quote is found on the page but the region cannot be resolved (multi-page or rotated text), the citation is verified and highlighted by quote search.

4. **No stored quote text.** `citations` has no quote column. It stores only `quote_sha256`, the SHA-256 of the words read from the word layer inside the resolved region. On display the server re-reads the quote from the **masked** word layer of the cited evidence version and compares it with `quote_sha256`. It returns `quote_state = shown`, `withheld` (the reader may not see the text, or the layer is gone with its version) or `changed` (the hash does not match). Verification runs on the masked projection, so quotes an agent copies from masked text still verify. A masked TIN is never unmasked to verify a quote. `value_text` (Confidential) is stored, because number provenance and the linked-figure card compare against it.

5. **Display is rendered by code.** `GET /v1/citations/{id}` returns the display contract (`CitationDisplay`, C4). Its `title` and `loc` are rendered by the kind's display function from the locator, never from model text.

6. **Moved and broken are computed from insert-only `citation_events`.** A citation's state is `valid`, `moved`, `broken` or `relinked`. `relinked` is the old row after a person re-linked it; the new row is `valid`. Nothing stores the state on the citation row; it is computed from the latest event, else `valid` (the repo's "staleness is computed" pattern), and exposed through the read view `citation_current`.
   - **`moved`.** The evidence module's outbox consumer of `evidence_version.created` writes one `citation_events(kind=moved)` row and one `citation.moved` outbox event for each citation of the replaced version, within one relay cycle. Methodology and workpaper owners call `evidence.api.mark_sources_superseded(tx, …)` in their own unit of work.
   - **`broken`.** A voided, withdrawn (ADR-162) or erased source gets a `broken` event.
   - `citation_events` (`moved`, `broken`, `relinked`) is insert-only for every role.

7. **Relink is a human act.** `POST /v1/citations/{id}/relink` re-reads the old text from the old, immutable layer and looks for it on the successor. If it is found, the server writes a **new** verified citation with `supersedes_id`, a `relinked` event naming the person, and a `citation.relinked` audit event. If it is not found, the answer is `422 relink_unverified`, and the person opens the source and cites again. Three layers refuse an agent, a worker, or any caller outside a live API request:
   - the matrix: `citation.relink` denies agent;
   - the `serving_request()` guard;
   - a database CHECK: `kind <> 'relinked' OR actor_kind = 'human'`.

8. **Reserved `annotation_id` locator slot.** The `document_text` locator carries an optional `annotation_id`, reserved and always null in P-03. When SHL-08g Annotate lands (K-03, S52–S60, with `evidence_annotations`), an annotation is cited as `document_text` with `annotation_id` set, and the `document_text` verifier accepts it. Annotations never become an eleventh kind.

9. **Reserved human create.** `POST /v1/citations` ("Cite selection") is frozen in the C4 stub and answers 501 until its first anchor consumer lands (P-04, SHL-09). The server derives the quote from the layer and ignores any client-sent text. The matrix action is `citation.create`, and agent is denied.

10. **Number provenance (the rule; enforcement lands with P-10).** In agent blocks, every numeric token must be one of two things: a `{fact: "fNN"}` reference to a code-computed fact, rendered by code, or equal to the `value_text` of a verified citation. Any other number is repaired once, and otherwise shown as "Unsupported". P-03 ships the data this needs (verified `value_text`, `citations.verified`). The check itself is enforced on P-24 AgentBlocks structured output in P-10 (S29–S38). P-03 changes no existing agent behaviour.

## Options considered
### Option A: first-class insert-only rows in `evidence`, hash-only quotes, computed state — chosen
- Pros:
  - One table every surface reads; P-04, P-10 and F-04's INV-2 checker share it.
  - Immutability and walls are enforced in one place (`visible()`, 404).
  - No second copy of Restricted text.
  - Supersession is recorded, never overwritten.
- Cons:
  - Display needs a layer read per quote.
  - Quotes become `withheld` when their version is crypto-shredded. That is the intended effect.

### Option B: citations as JSONB on outputs plus a `citation_index` in `agents` (chapter 05 sketch)
- Pros: close to the current `handoff.Citation`.
- Cons:
  - Two sources of truth.
  - `evidence` would depend on `agents` to find citations to its versions, which reverses the module graph (ADR-137).
  - Human citations would need a different home.
- Why rejected: chapter 09's glossary row puts `citations` (v2) and `citation_events` in `evidence`, and P-03 §4.1 settles it there.

### Option C: store the quote text and a mutable `state` column
- Pros: cheaper reads, no layer dependency.
- Cons:
  - A second copy of Restricted text outside the version's retention and shred.
  - UPDATEs on an audit-grade record.
  - A stale `state` if a consumer misses an event.
- Why rejected: it breaks ADR-004's pattern and the data-minimisation reason for hashing.

## Consequences
**Positive**
- Every citation a person sees was verified by code and resolves to a region, cell or record (INV-2).
- "Source moved" and re-link work across every source kind without editing old rows.
- Annotations and Cite selection have their slots before their epics start, so C4 v1 does not break when they land.

**Negative / costs accepted**
- Seven kinds have no verifier until their owner modules land (K-01, A-02, A-04, K-03, T-04, T-05, P-04, P-10). Until then those kinds are written unverified.
- The display path depends on the word layer (P-03-T05). A version with no layer shows `quote_state=withheld`, and highlighting falls back to quote search.

**Follow-up work created**
- Code: P-03-T02 (C4 stub models and routes), P-03-T04 (migration `trust_kit_v1`), P-03-T08 to T10 (verifiers, display, agent writes), P-03-T12 (moved detector and relink), P-03-T17 (`evals/citations/suite.yaml`).
- Specs: SPEC-322 (trust kit v1).
- Contract: `docs/contracts/c04-citations-viewer.md` (C4 v1).
- Glossary: `citation`, `citation_event`, `evidence_page` / word layer, `pii_region`, `pii_reveal`, `evidence_derivation`.
- Matrix: `citation.read`, `citation.relink`, `citation.create` (evidence section).
- Registry: `evidence/registry.py` (`citations`, `citation_events` in `INSERT_ONLY_TABLES`).
- Later: K-03 (`annotation_id`, SHL-08g); P-04 (Cite selection, `register_citing_anchor`); P-10 (number-provenance enforcement).

## Enforcement
- [ ] Lint rule: none; the rules sit in the schema and the service.
- [x] Architecture / dependency rule in CI: `agents` depends on `evidence.api`, never the reverse (import-linter, ADR-137).
- [x] Test: P-03-T03 (C4 consumer suite) and the P-03 independent suites cover insert-only rows (AC1.4), no quote column, the human-only relink CHECK, verify-before-display reasons and the ten-kind enum. `evals/citations/suite.yaml` catches fabricated page, bbox, quote, value, zero-width and moved cases at 1.0.
- [x] Hook or protected path: `evidence/**`, `agents/{citations.py, document_citations.py, handoff.py}`, `backend/migrations/versions/*`, `evals/**`.
- [x] Reviewer agent checklist item: architecture and AI reviewers check that no quote text is persisted and that no agent path writes a `relinked` event.

## Guidance for agents
Write citations only through `evidence.api.record_citations` in the same unit of work as the output that cites them. Never store a quote string. Never render `title` or `loc` from model text. Never UPDATE a citation to change its source; record an event, or write a new row with `supersedes_id`.

**Do**
```python
await evidence_api.record_citations(tx, run_id=run.id, citations=[
    DocumentTextLocator(evidence_version_id=v.id, page=3, bbox=None, annotation_id=None),
])  # the server hashes the words it reads; verified/verification_reason are computed
```

**Don't**
```python
session.add(Citation(quote="Total investments 16,500,000.00", state="moved"))  # no quote column; state is computed
```

## Revisit when
- A source kind outside the ten needs citing. A new ADR decides it; annotations are not such a case.
- Cross-document content search is wanted. That needs a tenant-keyed encryption ADR (chapter 03).
- Display latency of the layer re-read exceeds the SHL-07 hover budget at scale.

## Related
- ADRs: ADR-004, ADR-005, ADR-031, ADR-034, ADR-054, ADR-066 (extended, not superseded), ADR-104, ADR-110, ADR-137, ADR-145, ADR-160, ADR-161, ADR-162.
- Specs: SPEC-322.
- Docs: `docs/plan/03-backend-architecture.md` §3.7.2; `docs/plan/05-agent-architecture.md` §5.3.10; `docs/plan/epics/P-03.md` §§3, 4.2, 4.3, 6; `docs/contracts/c04-citations-viewer.md`; `docs/plan/09-decisions-adrs.md` (P-48).
