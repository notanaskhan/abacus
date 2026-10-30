---
id: SPEC-520
title: Document services, part 1 (the renderer, C11)
status: approved
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-007, ADR-042, ADR-052, ADR-110, ADR-320, ADR-321]
related_specs: [SPEC-400]
created: 2026-10-29
updated: 2026-10-29
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
P-11's renderer slice: templates as database content, deterministic PDF and DOCX renders of
DocBlocks through code-owned layouts (ADR-320), the generated-document lifecycle (Drafting · Draft
· Approved · Locked · Out of date), field regions, and the bytes stored as evidence, all behind the
C11 contract (`docs/contracts/c11-renderer.md`). OCR and extraction (ADR-321, C4 v1.1) are part 2:
their criteria join this spec with P-11-T19.

## 2. Problem and context
Letters, consents, reports, notice responses and packages are produced outside the platform today
or uploaded after signature. A reviewer cannot prove the letter approved is the letter signed, and
wording changes need an engineer. The consumers (ENG-04, AUD-20…23, TAX-12, NOT-03, CLS-08,
FSP-06; P-10 trace exports; F-07's test faces) need one renderer with one contract.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Quality partner / practice leader (Margaret) | Publishes a template version (fresh MFA) |
| Firm admin, quality partner, practice leader (Grace) | Imports template bundles (dry run, draft) |
| Engagement team (Priya, Hannah) | Renders drafts, regenerates, approves through the consumer's own action |
| Accrued Agent | Requests drafts only, through a consumer service (INV-1) |
| System (relay) | Marks documents out of date from registered source events |

## 4. Goals and non-goals
**Goals**: C11 v1 stub then implementation; templates in the database; byte-identical renders;
draft/final/locked lifecycle with human-only finals; field regions; evidence storage.

**Non-goals**: filed tax forms or final K-1s (DEC-78); merging client PDFs into packages (OQ-5);
model-written template text (ADR-230); any client route (clients read through C10 and C7); OCR (part 2).

## 5. User stories and acceptance criteria
The plan's F-numbered criteria (`docs/plan/epics/P-11.md` §3) map to AC-n as below, verbatim in
meaning.

### Story 1 (F1): templates are database content
- **AC-1** (AC1.1) Given a template bundle, when `POST /v1/report-templates/import?dry_run=true` runs, then every error is listed by path (`unknown_variable`, `unknown_layout`, `unknown_block`, `markup_not_allowed`, `clause_conflict`, `too_large`) and nothing is stored; with `dry_run=false` and no errors a draft version is stored insert-only with its `content_sha256` and `report_template.imported` is audited naming the importer.
- **AC-2** (AC1.2) Given a body with HTML, CSS, a URL or an expression outside `{"var": "<declared key>"}`, then import refuses `markup_not_allowed`.
- **AC-3** (AC1.3) Given a draft version, when a quality partner or practice leader publishes it with fresh MFA, then a publication row and `report_template.published` are written; an agent, worker or client principal is refused.
- **AC-4** (AC1.4) Given a published version, then nothing changes it; a correction is a new version and republishing a prior version rolls back without a deploy.
- **AC-5** (AC1.5) Given the repo, then a CI scan finds no template wording in migrations, constants or fixtures outside the synthetic Brightwater Hale scenario.

### Story 2 (F2): deterministic PDF render
- **AC-6** (AC2.1) Same template version, snapshot, clause states, overrides and engine version → identical PDF bytes across two runs and two containers.
- **AC-7** (AC2.2) Every page of a draft carries the DRAFT watermark.
- **AC-8** (AC2.3) Hostile variable text (`<script>`, `=HYPERLINK(…)`, `{{…}}`, zero-width or bidi characters) renders as literal text.
- **AC-9** (AC2.4) Any URL in a template, asset reference or value is refused by the fetcher: `asset_not_allowed`.
- **AC-10** (AC2.5) An unresolvable declared variable refuses 422 `missing_variable {keys}`, never a blank.
- **AC-11** (AC2.6) An AR-C 70 package carries its legend on every page.
- **AC-12** (AC2.7) A §7216 consent renders as its own document from `consent_7216` at the layout's minimum type size.
- **AC-13** (AC2.8) A letter ≤ 10 pages renders at p95 ≤ 10 s; a package ≤ 60 pages ≤ 60 s.

### Story 3 (F3): generated-document lifecycle
- **AC-14** (AC3.1) Status is computed: Drafting (a render job queued or running) · Draft · Approved (latest final) · Locked (a lock event), with an Out of date overlay.
- **AC-15** (AC3.2) A final render needs a human approval resolved through the kind's approval provider whose `content_hash` equals the draft's; otherwise 422 `final_requires_approval` or 409 `approval_hash_mismatch`; the database refuses a final version with a non-human requester.
- **AC-16** (AC3.3) An agent-requested render is a draft with `requested_by_kind=agent` and its run id; the audit reads "<person> via Agent".
- **AC-17** (AC3.4) A registered source event whose values differ from the snapshot writes an `out_of_date` event within one relay cycle and `GET …/changes` lists the changed variables; an engine upgrade never marks a document out of date.
- **AC-18** (AC3.5) Regenerate (human-only, Idempotency-Key) creates version n+1 as a draft; version n stays immutable; sign-offs on n go stale; agent and worker contexts are refused.
- **AC-19** (AC3.6) A locked document answers 409 `document_locked` to regenerate and final render.

### Story 4 (F4): DOCX
- **AC-20** (AC4.1) The DOCX is built from the same DocBlocks with fixed properties and sorted, fixed-timestamp ZIP entries; two runs give identical bytes.
- **AC-21** (AC4.2) The DOCX text equals the PDF's extracted text block for block on the golden fixtures.

### Story 5 (F5): regions and traceability
- **AC-22** (AC5.1) Every variable occurrence and fixed-layout field yields a field row `{field_key, label, page, rect_pt, value_text, match_id}` served by `GET …/versions/{n}/fields`.
- **AC-23** (AC5.2) `GET …/compare?to=standard` is a deterministic word-level diff by block and clause id.
- **AC-24** (AC5.3) A generated version's pages flow through P-03's `words` step, so citations into it are ordinary `document_text` citations that verify.

### Story 6 (F6): generated documents are evidence
- **AC-25** (AC6.1) Each format is one evidence version with `channel=generated`, Object Lock, the kind's retention record type and provenance facts; its fingerprint equals `render_hash`.
- **AC-26** (AC6.2) `visible()` and walls apply as for uploads (walled users 404, no count); client principals get 403 on every P-11 route.
- **AC-27** (AC6.3) UPDATE and DELETE of generated versions, files, fields and events are refused for every role.

### Story 7 (F11): contract-first delivery
- **AC-28** (AC11.1) The C11 stub's consumer suite runs in the provider's CI and stays green through every later P-11 PR; C11 v1 freezes at the S18 Contract Monday.

### Task acceptance (S17 rows, verbatim)
- **AC-29** (P-11-T01) Both ADRs cite DEC-16, DEC-42, DEC-44, ADR-042 and ADR-110, state the rule-6 position for Textract, and are accepted before the C11 stub merges.
- **AC-30** (P-11-T02) A three-page letter fixture renders byte-identical PDF and DOCX in two fresh containers and in CI, or the Typst fallback is recorded.
- **AC-31** (P-11-T03) The generated client exposes every C11 route returning seed-derived fixtures, each route declares one matrix action, and agent principals are refused final renders, regeneration and template publication.
- **AC-32** (P-11-T04) The consumer suite asserts shapes, refusal codes (`missing_variable`, `final_requires_approval`, `document_locked`), human-only actions and audit event names, and runs green in the provider's CI.
- **AC-33** (P-11-T05) Every table is tenant-RLS; versions, files, fields and events reject UPDATE and DELETE for every role; the mode CHECKs hold; the single-head check passes.

## 6. Behaviour and flows
`docs/plan/epics/P-11.md` §4.2 (tables), §4.3 (endpoints and matrix rows), §4.4 (renderer rules),
§4.6–§4.8 (workflow, outbox, audit) and §8.1 (C11 shapes) are the behaviour, as amended by
ADR-320. Flag `reporting.generated_documents` (per firm, default off) gates every C11 route: off
answers 404 as the C7 stub does.

## 7. Data and permissions
Tables `generated_documents`, `generated_document_versions`, `generated_document_files`,
`generated_document_fields`, `generated_document_events`, `render_jobs` (P-11-T05) and the
`report_template*` tables (P-11-T06). Matrix actions `generated_document.read`,
`generated_document.regenerate`, `report_template.read`, `report_template.import`,
`report_template.publish` (P-11 §4.3). No client role reaches any of them.

## 8. Open questions
None blocking. OQ-4 (import and publish rights) takes the plan's default: import by firm_admin,
quality_partner, practice_leader; publish by quality_partner or practice_leader, a different person
from the importer. OQ-7 (consent layout) takes 12-point minimum, US Letter, separate document until
counsel answers.
