---
id: RB-43
title: Document services (part 1 renders, engine upgrade, template rollback; part 2 OCR, kill switch, backfill, yearly form-map refresh)
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-08-20
---

# RB-43 · Document services

P-11-T17 (P-11 §4.10, R4; ADR-320) wrote part 1 (§1–§8: renders). Part 2 (§9–§14: OCR, the
kill switch, the backfill, the yearly form-map refresh) is P-11-T38 (S34). The row named `docs/runbooks/document-services.md`; it carries the next free
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

## 9. OCR is down or slow (Textract outage)
RB-47 holds the alarms (`textract-throttled`, `textract-usererrorcount`,
`textract-servererrorcount`) and their first steps; this section is what a firm sees.
1. Nothing is lost: an upload lands as an evidence version whatever OCR does, and the viewer shows
   the page image. A page OCR could not read is `not_scannable`; the inbox and TAX-03 show manual
   entry for its fields (P-11 §4.10).
2. A regional Textract outage: set the kill switch (§11) so pages stop reaching a failing
   provider and no firm piles up refusals; tell the firms that OCR is paused (the status page).
3. When AWS reports recovery: lift the kill switch, then run the backfill (§12) for each firm that
   uploaded during the outage. The backfill reads only pages with no words and no OCR row yet.

## 10. Refusal spikes
Every OCR call goes through the gate first (`evidence/ocr_gate.py`, P-11-T23), and the first failing
condition is the reason, written to the insert-only `ocr_runs` row with identifiers and counts only.
A refusal is never retried automatically and never rerouted. Read the spike by reason:

| Reason | What it means | Do |
|---|---|---|
| `kill_switch` | `model_route_block` on route `textract` is set | Expected during §9/§11; otherwise find who set it (audit trail) |
| `flag_off` | the firm's `evidence.ocr` is off | Expected before a firm's flip (RB-68); a spike after a flip means the flag was turned off |
| `terms_not_covering` | no provider-terms entry covers `textract` today | RB-40: the entry expired or was never added; nothing reaches AWS until it is fixed |
| `boundary_basis` | a real firm without the AI-services opt-out evidence on its entry | RB-40; a synthetic firm never refuses on this |
| `consent_missing` | tax return information without the C19 consent the caller found | §7216: the firm collects consent (ADM-05); never override in code |
| `quota_exceeded` | the firm reached its daily page cap (§11) | Expected on bulk days; the cap is a refusal, never a queue |

A spike of `terms_not_covering`, `boundary_basis` or `consent_missing` is a compliance signal, not
an outage: raise it with the firm's admin the same day.

## 11. Cost cap and the kill switch
- **Daily page cap:** 5,000 pages per firm per day (`DAILY_PAGE_CAP`, P-11 §cost). Pages over it
  refuse with `quota_exceeded`; the next day's first page runs. The 80% alarm and the December
  profile are RB-68's.
- **Kill switch, every firm:** set `model_route_block` on route `textract` in the platform console
  (ADR-140). The gate refuses the next page; calls in flight finish. Lift it the same way.
- **One firm:** turn its `evidence.ocr` flag off (per firm, RB-68 §flip). Form extraction follows:
  `evidence.form_extraction` off writes no fields and consumers show manual entry.
Neither switch changes evidence: versions, fingerprints and the words already read stay.

## 12. Backfill (an ECS one-off task, never a laptop)
`python -m abacus_tools.ocr_backfill <tenant-id>` starts (or joins) the tenant's
`ocr_backfill:<tenant>` workflow on the background queue. It runs the same idempotent activities a
new upload runs, behind the same gate, in batches by cursor, and never changes evidence.
1. On staging or production, run it as an **ECS one-off task** of the API service's task definition
   with the command overridden (the ops request, `ops-task.yml`; staging: the ops one-off in
   `infra/README.md`). **Never from a laptop against a shared database** (AGENTS.md rule 17).
2. One firm at a time; the workflow id makes a second start join the first.
3. Watch `ocr_runs` for the tenant: refusals stop the page, not the backfill. A long scan (over
   20 pages) runs as `LongOcr` on the background queue.
4. Done when `pending_ocr` returns nothing for the tenant (the workflow completes).

## 13. Yearly form-map refresh (owner: ayushkbhatia)
The maps are repo parameter files, `backend/src/abacus/modules/evidence/forms/<form>/<tax_year>.yaml`
(DEC-76): reviewed yearly against the IRS form for the year. **Owner:** ayushkbhatia (the
`evidence.form_extraction` flag owner). **Due:** each Dec 1 for the coming tax year, before the
Jan 1 window.
1. For each form (1098, 1099-DIV, -G, -INT, -MISC, -NEC, -R, the notices), read the new year's IRS
   draft. Unchanged: add `<year>.yaml` with `inherits: <prior year>` and a new `version`. Changed:
   copy the prior map and edit anchors, boxes and code boxes.
2. **Golden corpus:** `backend/tests/golden/scanned_corpus.yaml` (P-11-T28) and the map tests
   (`tests/unit/evidence/test_p11t34_tax_form_maps.py`, `test_p11t35_tax_form_maps_part2.py`,
   `test_p11t37_form_extraction_independent.py`) gain the year's cases; an unsupported year must
   still yield no fields.
3. The change is a protected-path PR (maps are PROTECTED): golden tests green, both approvals,
   merged in the Dec bundle. No migration; old years' maps stay for re-reads.

## 14. Rehearse part 2 (staging drill)
On staging with the synthetic test firm PF-X1 (Brightwater Hale; DEC-1530), from this runbook only:
1. Set the kill switch; upload a scanned 1099-INT; confirm a `kill_switch` refusal row and the
   page image in the viewer; lift it.
2. Run §12's backfill as an ECS one-off task for PF-X1; confirm the page now has words and the
   fields appear (with `evidence.form_extraction` covering tax forms).
3. Record the drill in the rehearsal log below with the times.

## 15. Portal drops that do not sort (R-01-T09; `portal.drop_sort`)
A client's drop is sorted by code after extraction (`evidence/drops.py`, `upload_processing`
`patched("portal_drop_sort")`). A drop that is not linked is not lost: it stays `waiting` on the
binder and the engagement's leads get `portal.drop_unsorted`.
1. **Many drops waiting at one firm:** expected when files are ambiguous (the top request must
   match on kind plus a date or account and score twice the next). The leads file them; nothing to
   fix. Check the drop poll (`GET /v1/portal/drops/{batch_id}`) shows them received.
2. **No drop sorts anywhere:** the extraction step is failing (§4 and §6 above) or the
   upload-processing worker is down (RB-23): the sort runs only after extraction.
3. **A drop linked to the wrong request:** it was a rule fulfilment, a suggestion; the firm voids
   it with a reason (`POST …/fulfilments/{id}/void`) and links the right one. Never delete the
   version. If the dropper could not see the request it was linked to, that is RB-08.
4. **Contain:** `portal.drop_sort` off for the firm. Drops are still accepted and wait for the firm;
   only the automatic link stops.

## Rehearsal log

| Date | Who | Drill | Result |
|---|---|---|---|
| — | — | §6.3 staging drill | not yet run |
