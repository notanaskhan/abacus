---
id: SPEC-322
title: "Trust kit v1 (P-03): citations v2, the source viewer, masked PII with logged reveal, and password unlock"
status: approved
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-166, ADR-066, ADR-004, ADR-110, ADR-005, ADR-031, ADR-052, ADR-054, ADR-089, ADR-104, ADR-139, ADR-140, ADR-145, ADR-160, ADR-162]
related_specs: [SPEC-318, SPEC-319]
created: 2026-10-23
updated: 2026-10-23
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, add it to *Open questions*, then decide it with the plan's proposed option and record it (`docs/plan/AMENDMENT-solo.md` item 7).
> - Every test must reference the acceptance criterion (AC-n) it proves.

**Sources.** `docs/plan/epics/P-03.md` §§1–8 is the source for anything this spec leaves out:
- §3 has the epic's own acceptance numbering (AC1.1 to AC8.1). Each AC below names its epic AC in brackets.
- §4.2 has the tables, §4.3 the endpoints, §4.4 the masking rules and §4.9 the flags.

The binding contract is `docs/contracts/c04-citations-viewer.md` (C4 v1, freeze S5). The binding decision is ADR-166 (P-48; the plan's alias "ADR-144" means ADR-166). The open questions in P-03 §11.2 were decided in DEC-148. Screen letters follow the post-revision artboards. SHL-08g (Annotate) is planned for K-03 and is not in this spec.

## 1. Summary
Every citation in Accrued becomes a code-verified row that opens its source at a lit region (SHL-07 popover, SHL-08 viewer). Every page a person sees is a server-rendered PNG with taxpayer identifiers burned out. A named, onshore person with recent MFA can reveal one, and the reveal is logged. A password-protected PDF can be unlocked without the platform keeping the password or changing the evidence.

## 2. Problem and context
Today citations are page-and-quote JSONB on agent outputs (ADR-054, ADR-066). They have no region, no non-document kinds and no "source moved" state. Previews are unmasked (`EvidencePreview.tsx`). Password-locked uploads are dead ends. 58 inbound links to SHL-08 and 46 screens using SHL-07 wait on C4. Journeys J03, J04, J06, J08 and J16 cross these overlays.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Hannah Leclerc (Audit Senior Manager) | Reads citations, steps stacks, re-links moved citations, uses the dock viewer |
| Simone Baptiste (Senior) | Opens an uploaded document at the quoted region |
| Samuel Ito (Tax Manager) | Reveals a masked SSN on the record; unlocks a password PDF |
| Felix Andersen (`security_admin`) | Answers "who saw this SSN" from the reveal log (RB-31) |
| Lena Park (walled from Ashford) | Gets 404, never a count |
| Offshore member | Sees masked values only; is refused unscannable pages |
| Client principal, `client_service`, platform support | Never read citations, regions or reveals |
| Accrued Agent | Writes verified citations; never reveals, unlocks or re-links; sees masked text only |

## 4. Goals and non-goals
**Goals:**
- C4 v1: citations v2, the viewer manifest, pages, regions, search, reveal, unlock, and the reserved create.
- The `trust_kit_v1` migration.
- Word layer, PII scan and masked previews as patched steps of `upload_processing`.
- The moved detector and relink.
- SHL-07 a–e and SHL-08 a–f and h, on F-05's L2 shells.
- Agent citations persisted as v2 rows; agents see masked material.
- `evals/citations`.

**Non-goals** (P-03 §2.3):
- SHL-08g Annotate (K-03).
- Cite selection beyond the reserved 501 route (P-04).
- OCR for scanned pages (P-11).
- Tax-form field extraction (P-11, T-04).
- Verifiers for the seven kinds whose sources do not exist yet.
- Number-provenance enforcement on agent prose (P-10).
- The lineage tab (A-10).
- Hi-DPI re-render and raising the 50-page cap.
- Cross-document search.
- Inbox-file viewer manifests (N-01).

## 5. User stories and acceptance criteria

### Story 1: a citation is a first-class, verified record (C4 core; ADR-166)
- **AC-1** [AC1.1] Given the screener cites page 3 of a Harborline statement with a quote, when its handoff is recorded, then one `citations` row is written:
  - `kind=document_text`, `created_by_kind=agent`, `created_by_run_id` set;
  - `quote_sha256` is the hash of the word-layer words inside the resolved bbox;
  - no quote text is stored anywhere in the row.
- **AC-2** [AC1.2] Given a citation to page 9 of a 3-page file, a bbox with no words, a quote absent from the page, or a value that differs from the cell, then the row is stored `verified=false` with `verification_reason` in {`page_not_found`, `bbox_mismatch`, `quote_not_found`, `value_mismatch`}, and every reader shows "Unverified".
- **AC-3** [AC1.3] Given a valid quote whose bbox cannot be resolved (multi-page or rotated text), then the citation is verified on page text and highlights by quote search. It is never failed only for a missing bbox.
- **AC-4** [AC1.4] Given any UPDATE, DELETE or TRUNCATE on `citations` or `citation_events`, then the database rejects it for every role.
- **AC-5** [AC1.5] Given Ashford citations and Lena Park:
  - `GET /v1/citations/{id}` answers 404;
  - a stack list omits the citation, with no hidden count.

  Given a client principal, every C4 citation route answers 403.

### Story 2: the citation popover (SHL-07 a–e)
- **AC-6** [AC2.1, SHL-07a] Given a cited cell with one citation, when Hannah hovers for 150 ms:
  - the cell lights (#E4D1E9, ring #BF99C8, ink #9253A2) and its row lights (#ECD9F0);
  - a 372-px popover opens 8 px beside the cell, with header "BH-EBP-110: General Planning Procedures", the step text and the footer "1 citation";
  - `title` and `loc` come from the server, rendered by code from the locator.
- **AC-7** [AC2.2, SHL-07b] Given three citations on one cell:
  - the header shows "‹ 1 / 3 ›" and two ghost edges peek 4 and 8 px below;
  - › and ‹ re-light each source in turn;
  - source 2 shows "Keystone SOC 1 Type 2 report, Oct 1 2024 – Sep 30 2025 · Section I, p. 3", its quote through `AgentText`, and a 120×80 masked thumbnail cropped to the region;
  - the footer reads "3 citations".
- **AC-8** [AC2.3, SHL-07c] Given a `methodology_step` citation on AUD-05:
  - the popover is 420 wide, with no doc icon and no footer;
  - the program text renders as plain text;
  - ↗ opens KNW-03 at the step only when that route is registered. Otherwise ↗ is hidden.
- **AC-9** [AC2.4, SHL-07d] Given a hover, then the preview renders at 95% opacity and closes 140 ms after the pointer leaves. A click pins it, and the cell keeps its ring. Escape closes it, the purple fades over 360 ms, and focus returns to the cell.
- **AC-10** [AC2.5, AC6.1, SHL-07e] Given a citation whose source was superseded:
  - the state is `moved`, computed from a `citation_events(kind=moved)` row written within one relay cycle of `evidence_version.created`;
  - the body reads "Source moved — BH-EBP-110 v2 was superseded by EBP v3 on Jan 1, 2026" in #8E2418;
  - "Re-link…" shows only when `allowed_actions` contains `citation.relink`.

  A voided, withdrawn or erased source gives `broken`.
- **AC-11** [AC2.6] Given the footer chips, when "Citations (n)" or "Procedures (n)" is clicked, then a 420-wide list opens from `GET /v1/citations?host_ref=…&section_id=…`. The list holds either the section's citations or its distinct `methodology_step` citations.
- **AC-12** [AC2.7] Given any citation with `verified=false`, then the marker renders "Unverified", the popover says so, and no quote is styled as a finding.

### Story 3: the source viewer core (SHL-08 a, b, e, f, h)
- **AC-13** [AC3.1, SHL-08a] Given `openSourceViewer({evidenceVersionId, matchId})`, then:
  - the O2 drawer opens at `?ov=viewer:<v>:<match>`;
  - the page shows the server-rendered masked PNG;
  - the region is lit with the label "Form 1040 · line 2a 1,550", and the page scrolls so the region sits 30% from the top.

  Back closes the drawer.
- **AC-14** [AC3.2, SHL-08a] Given the "Linked figure · Form 1040 line 2a" card:
  - its rows are the verified citations from the opening record into this version, with values from `value_text` only (307,900 · 4,600 · 1,550);
  - the active row is lit in the region's purple;
  - "Source 1 of 3 ‹ ›" steps the stack, and "Also cited: …" lists the other members.
- **AC-15** [AC3.3, SHL-08b] Given AUD-06 with `?dock=viewer`:
  - the dock shows Agent · Viewer · Notes with Viewer on, the compact `.evbar` and "2 / 3";
  - TOTAL INVESTMENTS 16,500,000.00 is lit;
  - clicking another trial-balance row re-targets the viewer without closing it.

  The fixtures foot: 14,895,000.00 + 1,605,000.00 = 16,500,000.00, and 16,500,000.00 + 312,400.00 = 16,812,400.00.
- **AC-16** [AC3.4, SHL-08e] Given a version whose word layer or masked rendition is not ready, then:
  - the manifest returns `status=processing`;
  - the viewer shows three pulsing skeleton pages and the "Processing…" muted pill;
  - the viewer polls every 3 s.
- **AC-17** [AC3.5, SHL-08f] Given the stack, when › is pressed, then source 2 of 3 ("Ridgeline 2025 K-1 statement, p. 3") loads with the 18A line lit.
- **AC-18** [AC3.6, SHL-08h] Given ⋯ "Auto-highlight cited fields" on (the default):
  - every region cited by a record the viewer can see has a 1 px #BF99C8 outline, with fill #ECD9F0 on hover;
  - turning it off removes the outlines;
  - the preference is per browser, and storage access is wrapped in try/catch.
- **AC-19** [AC3.7] Given any viewer state:
  - the toolbar has no Download and no select tool;
  - Download sits only in the header ⋯ ("Download · Open in Files") and uses the existing audited content route;
  - no raw file, pdf.js or SheetJS renders in the browser.
- **AC-20** [AC3.8] Given an XLSX or CSV, then the viewer shows the extraction table with the cited cell lit and zoom and rotate hidden. Masked cells show their mask token.
- **AC-21** [AC3.9] Given a search term, then hits come back as page rects only, with no text and at most 200 hits, and the query string is never logged.
- **AC-22** [AC3.10] Given any manifest, page, region or citation read before ADR-158 (P-40) lands, then the version belongs to an engagement and is authorised through `visible()` with ADR-145's scope kinds. Walled or invisible versions answer 404.

### Story 4: masked PII and the logged reveal (SHL-08c)
- **AC-23** [AC4.1] Given the seeded W-2 with "000-00-6081" under the box-a label, when it is processed, then a `pii_regions` row exists with `kind=ssn`, `last4=6081` and a sealed value. Label-anchored matches are masked even when the number fails validity rules. Unlabelled matches must pass the validity and checksum rules (P-03 §4.4).
- **AC-24** [AC4.2] Given any page image served by any route, then the pixels in every detected region are opaque, and an unmasked rendition is never generated or stored. A preview made before masking answers 409 `preview_outdated`.
- **AC-25** [AC4.3] Given agent material for the same file, then the SSN appears only as "•••-••-6081", and quotes copied from masked text still verify.
- **AC-26** [AC4.4, SHL-08c] Given Samuel (onshore, on the engagement, MFA inside the window), when he presses Reveal (logged):
  - `POST …/pii-reveals` returns `{value, expires_in: 30}`;
  - a `pii_reveals` row, a `pii.revealed` audit event and an `access_events` row are written without the value;
  - the value shows for 30 s under "Revealed by Samuel Ito · 9:31 AM · logged to the audit trail", and the chip reads Hide;
  - the value re-masks on Hide, timeout, navigation or unmount.
- **AC-27** [AC4.5] Given MFA older than the window and a TIN kind, then the reveal answers 403 `mfa_required`, and the shell's step-up runs before a retry.
- **AC-28** [AC4.6] Given an offshore member, an agent context, a client principal, `client_service` or a platform-support break-glass session, then:
  - the reveal is refused;
  - `allowed_actions` omits `pii.reveal`, so no chip is rendered;
  - no value leaves the server.
- **AC-29** [AC4.7] Given 20 reveals by one user in an hour, then the 21st answers 429 `reveal_rate_limited`, and the dashboard alarm counts it.
- **AC-30** [AC4.8] Given a page with no text layer before P-11:
  - the manifest marks it `pii_scan: not_scannable`;
  - an onshore member sees the page with the muted line "Scanned page · personal data isn't detected automatically yet";
  - an offshore member is refused the page.

### Story 5: password unlock without breaking immutability (SHL-08d)
- **AC-31** [AC5.1, SHL-08d] Given a password-protected PDF:
  - the manifest returns `status=password_protected`;
  - the viewer shows the Lock tile, "This PDF is password-protected.", "Enter the password Halvard sent the client, or ask the client for it.", a Password field, Unlock, and "Ask Jonah & Claire Feld…";
  - "Ask Jonah & Claire Feld…" opens SHL-14 prefilled.
- **AC-32** [AC5.2] Given the right password, when Unlock is pressed:
  - one isolated child decrypts, extracts, builds the word layer, scans and renders masked pages;
  - the outputs are insert-only records linked to one `evidence_derivations` row;
  - the version's bytes and fingerprint are unchanged;
  - `evidence_version.unlocked` is audited and published.
- **AC-33** [AC5.3] Given a wrong password:
  - the answer is `{status: wrong_password, attempts_left}`, with "That password didn't open the file.";
  - after 5 failures in 15 minutes, the answer is 429 `unlock_rate_limited` with `retry_after`;
  - failures are audited by count only.
- **AC-34** [AC5.4] Given any unlock:
  - the password is a `SecretStr` and is never written to logs, the database, storage, Temporal or error tracking, and never echoed back;
  - the field uses `type=password` and `autocomplete=off`, and clears on submit.
- **AC-35** [AC5.5] Given an agent context or a client principal, then unlock is refused.

### Story 6: relink is a human act (SHL-07e)
- **AC-36** [AC6.2] Given Hannah on a moved citation, when she presses Re-link…, then:
  - the server reads the old text from the old layer and finds it on the successor;
  - it writes a new verified citation with `supersedes_id`, a `relinked` event and a `citation.relinked` audit event naming Hannah.

  If the text is gone, the answer is 422 `relink_unverified` and "Open source" is offered. A citation that has not moved answers 409 `not_moved`.
- **AC-37** [AC6.3] Given a relink from an agent context, a worker or outside a live API request, then three layers refuse it: the matrix, `serving_request()`, and the DB CHECK `kind <> 'relinked' OR actor_kind = 'human'`.

### Story 7: agents write v2 citations and see masked text
- **AC-38** [AC7.1] Given the screening, upload_review and matching suites run after P-03-T10 and T15, then `citation_verification` stays 1.0, and every other threshold holds.
- **AC-39** [AC7.2] Given `evals/citations/suite.yaml`:
  - fabricated page, bbox, quote, value, zero-width-character and moved cases are caught at 1.0;
  - valid cases are accepted at 1.0.
- **AC-40** [AC7.3] Given a synthetic document containing an SSN, when matcher or upload-reviewer material is built, then no unmasked TIN pattern is present (containment 1.0).

### Story 8: contract first (C4 v1)
- **AC-41** [AC8.1] Given the C4 stub (P-03-T02):
  - every route in `docs/contracts/c04-citations-viewer.md` §2 exists in the generated client and declares exactly one matrix action;
  - each route returns seed-derived fixtures behind its `evidence.*` flag (P-03 §4.9);
  - `POST /v1/citations` answers 501;
  - agent principals are denied every human-only action (`citation.relink`, `citation.create`, `pii.reveal`, `evidence.unlock`).
- **AC-42** [AC8.1] Given the consumer suite in `backend/tests/contracts/c04_citations_viewer/` (P-03-T03), then it asserts the shapes, refusal codes, human-only actions, audit event names and footing figures (14,895,000.00 + 1,605,000.00 = 16,500,000.00; 6,200 × 25% = 1,550). It runs in the provider's CI and stays green through every later P-03 PR.

## 6. Behaviour and flows
**Happy path (J04 slice).**
1. Simone Baptiste opens an AUD-03 row.
2. She hovers the screening citation (SHL-07a).
3. She clicks the document citation, and the SHL-08 drawer opens with the quoted region lit.

**Alternate paths:** moved → Re-link… (AC-36), or "Open source" (AC-36). Viewer states: processing (AC-16), password protected (AC-31), `unreadable` and `not_previewable` (both "Can't preview", DEC-148).

**State transitions**
| From | Event | To | Who can trigger |
|---|---|---|---|
| citation `valid` | `citation_events(moved)` | `moved` | system (moved detector), owner modules via `mark_sources_superseded` |
| citation `valid` or `moved` | `citation_events(broken)` | `broken` | system (void, withdrawal, erasure) |
| citation `moved` | relink | the old row reads `relinked` (computed; the row itself is unchanged); new row `valid` with `supersedes_id` | live human only |
| manifest `password_protected` | unlock | `ready` (derived records) | live human only |
| mask `masked` | reveal | value shown 30 s, then masked again | live onshore human only |

## 7. Domain and data changes
- **Entities:** `citations`, `citation_events`, `evidence_pages`, `pii_scan_runs`, `pii_regions`, `pii_reveals`, `evidence_derivations`. `upload_extractions` and `upload_previews` gain `derivation_id`, and `upload_previews` also gains `mask_version`. Columns, enums and constraints are as in P-03 §4.2.
- **Invariants:**
  - All new tables are tenant RLS and insert-only.
  - There is no quote column.
  - CHECK `verified OR verification_reason IS NOT NULL`; agent ⇒ `created_by_run_id`; human ⇒ `created_by_user_id`; `relinked` ⇒ `actor_kind = human`.
  - `pii_reveals.user_id` is NOT NULL.
- **Migrations:** one reversible migration, `trust_kit_v1` (P-03-T04). It replaces the one-per-version unique indexes with ones that include `derivation_id` (ADR-135, before Jun 1, 2027).
- **Versioning and immutability:** derived records never touch the evidence object or its fingerprint (ADR-004, ADR-110).
- **Retention:**
  - Derived records follow their parent version's retention, holds and crypto-shred.
  - `pii_reveals` is kept as an access log for at least the engagement's retention.
  - Passwords are never kept.

## 8. Interfaces
Every operation, shape, refusal code, flag and audit event is in `docs/contracts/c04-citations-viewer.md`, which follows P-03 §4.3 exactly. Module interfaces in `evidence.api`:
- `record_citations(tx, …)`;
- `mark_sources_superseded(tx, source_type, source_id, old, new)`;
- `register_citable(kind, verifier, display)`.

`register_citing_anchor` is reserved for P-04. The outbox events are `citation.moved` and `evidence_version.unlocked`; `evidence_version.created` gains a subscriber.

## 9. Authorisation and tenancy
- **Tenant scoping:** `tenant_session(ctx)`, and RLS on every new table.
- **Who can do what:** the matrix rows `citation.read`, `citation.relink`, `citation.create`, `pii.reveal` and `evidence.unlock` (P-03 §4.3; contract §2). `evidence.read` is unchanged.
- **Engagement-level access:** `authorise`, then `visible()` with ADR-145's engagement and work-item scope kinds. `independence: required` on every new action.
- **Ethical walls / independence:** walls answer 404 and stacks carry no hidden count (DEC-43).
- **Client-side access:** none. Client roles are denied every C4 action (INV-4).

## 10. AI behaviour
No new model call, prompt or tool. The screener, upload reviewer and matcher keep their prompts. Their verified citations become v2 rows (`created_by_kind=agent`), and their material is built from the masked projection. Evals: `evals/citations` is code-only and blocking at 1.0; the three model suites keep their existing thresholds; `citation_region_resolved` is report-only (P-03 §6).

## 11. Integrations
None external. Storage (ADR-104 per-object keys) and Temporal already exist. Unlock is deliberately not a workflow, so a password never enters Temporal. The patched `upload_processing` steps v4 `words`, v5 `pii_scan` and v6 `masked_preview` are idempotent on (source, component version). The backfill runs as an ECS one-off task, never from a laptop.

## 12. Edge cases and failure modes
- A bbox with no words, a page beyond the count, or a rotated or multi-page quote (AC-2, AC-3).
- A pre-masking preview (409 `preview_outdated`).
- A scanned page (`not_scannable`; fail closed for offshore members).
- More than 50 pages: "This page isn't previewed (first 50 pages only)" (P-03 R12).
- A crypto-shredded version (`quote_state=withheld`).
- A hash mismatch (`quote_state=changed`).
- A citation into evidence the reader cannot see (omitted, no count).
- Rate limits (reveal 20 per hour; unlock 5 per 15 minutes).
- Zero-width and homoglyph quotes (evals).

## 13. Security and privacy
- **Classification:**
  - `pii_regions.value_sealed`, the reveal `value` and re-read quotes are Restricted (chapter 03 §3.7.2: quotes are Restricted client text);
  - `value_text` and `last4` are Confidential;
  - ids and geometry are Internal.
- **PII:** SSN, ITIN, EIN, bank account, routing number, DOB.
- **Secrets:** the unlock password, a `SecretStr` held only for the length of the request.
- **Threats:** hostile PDFs (ADR-052), prompt injection through quotes (`AgentText` only), TIN leakage into model context, leakage through logs and error tracking, and existence leaks through counts.
- **Mitigations:**
  - an isolated child for parsing and rendering;
  - opaque burned-in masks;
  - masked agent material;
  - scrubbers tested with a sentinel;
  - `no-store` and `nosniff` on pages and reveals;
  - 404 for walled resources.

## 14. Audit trail and evidence integrity
- **Actions logged:**
  - `citation.created`, with no quote;
  - `citation.relinked`;
  - `citation.moved` and `citation.broken`;
  - `pii.revealed`, with ids, kind and last4 only. It is audit-only and never fanned out;
  - `evidence_version.unlocked`;
  - `evidence_version.unlock_failed`, with a count only;
  - `evidence_version.read`, as today.

  Reveals also write `access_events`.
- **Provenance:** each citation records its version, page, region, verifier version and creator (agent run, or person on whose behalf it was made).
- **Immutable:** citations, citation events and every derived record. The evidence object and its fingerprint never change.

## 15. Observability
- **Logs:** never a quote, a value, a search query or a password.
- **Metrics:** reveals per user and per firm, unlock failures, `citation_region_resolved`, and moved-detector lag.
- **Alerts:** reveal volume, and unlock failures (RB-31).

## 16. Performance and scale
- Popover hover intent is 150 ms (DF-38).
- Pages are 1,240 px wide, with a 50-page cap.
- Search returns at most 200 hits.
- The moved detector finishes within one relay cycle.

## 17. UX
- **Screens:** SHL-07 (O1 popover; 372 wide, 420 for guidance) and SHL-08 (O2 drawer at 480, or the T2 dock pane at 330), on F-05's E1, E2, E5 and C-07.
- **States:** SHL-07 a–e, SHL-08 a–f and h.
- **Status words (C2):** added to `docs/product/status-vocabulary.yaml` by the C4 stub (P-03-T02), tied to `CitationV2Out.state` (`valid`, `moved`, `broken`, `relinked`), `ViewerManifestOut.status` (`processing`, `ready`, `password_protected`, `unreadable`, `not_previewable`) and `EvidenceUnlockOut.status` (`ready`, `wrong_password`). The words the screens show:
  - citation: Unverified · Source moved · Broken;
  - viewer: Processing… · Password-protected · Can't preview;
  - reveal: Revealed · logged.
- **Copy:** verbatim from the handoff and P-03 §3. Popover state is local, never in the URL.
- **Accessibility:** axe AA, keyboard paths, Escape order, forced colours and reduced motion.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-5, AC-36, AC-37 | integration (DB) | v2 rows, reasons, insert-only triggers, walls, relink CHECK (P-03-T18) |
| AC-6 to AC-12 | unit + e2e fixture | `shl-07-citation-popover.spec.ts` |
| AC-13 to AC-22 | unit + e2e fixture | `shl-08-source-viewer.spec.ts`; route tests for manifest, regions, search |
| AC-23 to AC-30 | integration + pixel + fullstack | detector golden tests; pixel opacity; `pii-reveal-unlock.fullstack.spec.ts` |
| AC-31 to AC-35 | integration + sentinel | fingerprint unchanged; sentinel password absent from every sink |
| AC-38 to AC-40 | eval | `evals/citations`, the three model suites |
| AC-41, AC-42 | contract | `backend/tests/contracts/c04_citations_viewer/` (P-03-T03), F-05-T44 TypeScript assertions |

## 19. Rollout
- **Feature flags** (ADR-089; per firm; default off; rollout only):
  - `evidence.citations_v2`;
  - `evidence.viewer_v1`;
  - `evidence.pii_reveal`, which is also the reveal kill switch;
  - `evidence.viewer_unlock`.

  Masking is never behind a flag. The new workflow steps run under `uploads.processing`.
- **Migration and backfill:** run `trust_kit_v1` in S5, then `trust_layer_backfill:<tenant>` on staging through an ECS one-off task.
- **Rollback:** turn the flags off, and the legacy `AiTag` link and the legacy (masked) preview return. The migration is reversible before go-live.

## 20. Open questions
None open. P-03 §11.2 OQ-1 to OQ-8 are decided with the plan's recommendations in DEC-148.

## 21. Future / explicitly deferred
- SHL-08g Annotate (K-03, through the reserved `annotation_id` slot).
- Cite selection (P-04).
- OCR words (P-11).
- Number-provenance enforcement (P-10).
- Lineage (A-10).
- `/v1/me/preferences` for auto-highlight, if users ask.
- A Re-link target picker (P-04).
