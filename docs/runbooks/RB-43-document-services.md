---
id: RB-43
title: Document services part 1 (failed renders, engine upgrade and golden re-baseline, template rollback)
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-08-20
---

# RB-43 · Document services, part 1

P-11-T17 (P-11 §4.10, R4; ADR-320). Part 2 (OCR: Textract outage, refusal spikes, cost cap, the
`ocr.textract` kill switch, backfill, the yearly form-map refresh) is P-11-T38 (S34) and lands in
this file as §9 onward. The row named `docs/runbooks/document-services.md`; it carries the next free
runbook number like every other (README rule).

| Field | Value |
|---|---|
| Owner | builder (AY partner-facing; N for the renderer) |
| Severity range | SEV3 to SEV2 (SEV2 when letters, 8879s or K-1s cannot render inside the Sep 1 – Oct 20 window) |
| Linked from | none yet (alarm: `render_failed` rate per kind, to wire with Q-04's dashboards) |
| SLO affected | none yet |
| Kill switches that apply | `reporting.generated_documents` (off: every `/v1/report-templates*` and `/v1/generated-documents*` route answers 404 and consumers keep record mode: upload the signed letter) |
| Flag owner and expiry | `reporting.generated_documents`: owner ayushkbhatia, expires 2027-04-21 (`docs/architecture/feature-flags/reporting.yaml`, override DEC-137), before the Sep 1 – Oct 20 window. Its renewal (RB-26's flag-expiry wave) must land outside the window: renew to a date after Oct 20, 2027 or retire it in the Thu Oct 21 batch |
| Rehearse by | Fri Aug 20, 2027 (the staging drill in §6.3) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

What never changes during any of this: an approved final render and a signed copy stay the record
(C11 AC-19, `document_locked`); no code path re-renders a locked document; a model never writes
document text (DEC-79); every value in a document is a typed variable resolved and formatted by
code (ADR-050).

## 1. Recognise it

- **A render failed.** The render job (`reporting/render_job.py`) marks the job `failed` with a
  code, writes a `generated_document_events` row of kind `render_failed`, audits it, and leaves no
  partial file. The document's newest version has no files; the consumer (ENG-04, AUD-21/22/23,
  NOT-03, FSP-06) shows its error state. Codes and what they mean:

  | Code | Meaning | Usually fixed by |
  |---|---|---|
  | `missing_variable` | A declared template variable resolved to nothing (never rendered blank) | The owner's data (an engagement fact, a client field), then regenerate |
  | `unknown_variable` | The template names a variable the kind does not declare | Republish a version without it (§6.3), then fix the template |
  | `markup_not_allowed` | A template part carries markup the bundle validation should have refused | Republish the prior version; file a defect against `templates.py` |
  | `asset_not_allowed` | A template reached for an asset outside the deny-all `asset:` fetcher | Same as above |
  | `missing_glyph` | A value carries a character no vendored font covers (Arimo, Gelasio, Geist Mono) | The value (a pasted symbol), or a font change through §5 |
  | `final_requires_approval`, `approval_hash_mismatch` | A final render without a matching person's approval | Nothing to fix in the renderer: the approval is missing or was for other content |
  | `document_locked` | A locked document asked to re-render | Nothing: it is the record |
  | `renderer_unavailable` | The isolated renderer child could not start or timed out | §2 and §6.1 |

- **An engine upgrade broke the goldens.** `make golden-render` (CI job `render-golden`) fails on a
  hash mismatch after a WeasyPrint, Pango, HarfBuzz, python-docx, font or layout change.
- **A template version is wrong.** A partner reports wrong words in every new letter of one kind,
  and the template version the documents name (`GET /v1/generated-documents/{id}` → `versions[].template`)
  is the newly published one.

Neighbours: an evidence store failure (`store_generated` errors; RB-24 if the scanner holds files)
and a workflow-engine outage (render jobs stuck `queued`; RB-23).

## 2. Contain

1. If renders fail for every kind (`renderer_unavailable` across firms): stop new requests from
   piling up by turning `reporting.generated_documents` off for the affected firms (`make flag`,
   the other founder approving). Consumers fall back to record mode: a letter is uploaded signed,
   and nothing already approved or signed is touched.
2. If one template version is wrong: republish the prior version now (§6.3); no deploy.
3. If one value is wrong in one document: nothing to contain; fix the data and regenerate (§6.2).

## 3. Preserve

The failed job's row (`render_jobs`: id, failure code, engine version), the `render_failed` event
and its audit row, and the template version id. Never copy the document's content, its variables
or a client's values into a ticket: name the document id and the variable key only.

## 4. Assess

Which kinds and firms; whether any final render, approval or envelope is waiting on it (letters
before an M11/M13 deadline, 8879s, K-1 packages); whether the window (Sep 1 – Oct 20) is open, in
which case the R4 rule holds: no renderer merge except a defect fix through the hotfix lane.

## 5. Engine upgrade and golden re-baseline (both approvals)

The renderer's bytes depend on `engine_version()`: the PDF and DOCX packages, the layouts' version
and the fonts manifest (`reporting/render/core.py`). An engine upgrade never marks a document out
of date and never changes a document's `content_hash` (AC-17): old documents keep their files,
and only new renders use the new engine.

1. Upgrade on a branch (outside S22 – S26; R4). Run `make golden-render`: it renders the golden
   letter in two fresh containers with no network, compares them with each other and with
   `backend/tests/golden_render/letter.{pdf,docx}.sha256`, then runs the image-bound suite.
2. The two containers must agree. If they differ, the engine is not deterministic: stop; the
   upgrade does not ship.
3. If they agree but differ from the recorded goldens, inspect the two PDFs side by side (the
   render must still be the designed letter: watermark, legend, consent floor, every glyph).
4. Re-baseline only with **both founders' approval** recorded on the pull request (the reviewer
   is never the person who changed the engine): `RECORD_GOLDEN=1 make golden-render`, then commit
   the two `.sha256` files and the `p11t12.sha256` fixture hashes with the upgrade, in one PR.
5. Never re-baseline by editing a hash by hand, and never to make an unexplained difference pass.

## 6. Recover

### 6.1 The renderer is unavailable

Check the worker-batch service's tasks and the renderer image's pinned Pango and HarfBuzz (the
child imports WeasyPrint only inside the isolated process). Redeploy the previous image if a deploy
caused it (RB-01). Then turn `reporting.generated_documents` back on and regenerate the documents
whose newest version failed (§6.2).

### 6.2 Regenerate a failed or changed document

A person (never the agent or a worker) asks for version n+1: `POST
/v1/generated-documents/{id}/regenerate` with an `Idempotency-Key` (a retry with the same key
replays and renders nothing twice). Regenerate keeps the newest version's sealed snapshot and
template version, puts each value the kind's provider answers now in place of the sealed one, and
renders a draft. A locked document answers 409 `document_locked`.

### 6.3 Roll a template back by republishing a prior version (no deploy)

Templates are database content (`methodology` report templates, imported through the admin
endpoint, never committed). A bad version is rolled back by publishing the previous one again:

1. `GET /v1/report-templates` lists the firm's templates with their versions (`GET
   /v1/report-templates/{template_id}/versions/{n}` reads one); pick the last good version.
2. A partner other than that version's importer publishes it: `POST
   /v1/report-templates/{template_id}/versions/{n}/publish` (human only, fresh second factor;
   `PublisherIsImporter` otherwise). It becomes the current version at once; the bad version stays
   on record, never deleted.
3. New renders use it immediately. A document already drawn from the bad version keeps its
   template version on regenerate (§6.2), so a draft is re-drawn from the republished version by
   its consumer: for an engagement letter, ENG-04's Draft save (`PUT
   /v1/engagements/{id}/letter/composer` with the republished `template_version_id`) renders a new
   draft version. Approved and signed documents are not touched.
4. Check: the new draft's `versions[].template` names the republished version, and its PDF reads
   right in SHL-08.

**Staging drill (P-11-T17 acceptance; rehearse by Fri Aug 20, 2027).** On the synthetic firm: import
a deliberately changed version of the Brightwater Hale engagement letter template and publish it
(Margaret approving, Priya importing), render the Copperleaf draft, then republish the prior
version and save the Copperleaf draft again. Pass: the new draft names the prior template version,
renders without a deploy, and the audit trail shows both publishes by name. Record the run in the
rehearsal log below.

## 7. Verify

`render_failed` events stop for the kind; the newest version of each affected document has files;
`make golden-render` is green on main; the full-stack journey `render-letter.fullstack.spec.ts`
(P-11-T16) passes on staging the next night.

## 8. Review

Open the blameless review. A new failure code becomes a row in §1; a template that slipped past
bundle validation becomes a validation rule and a test in `templates.py`; an engine drift becomes
a pin. Update this runbook and set "Last reviewed against an incident".

## Rehearsal log

| Date | Who | Drill | Result |
|---|---|---|---|
| — | — | §6.3 staging drill | not yet run |
