---
id: SPEC-646
title: R-02 portal approvals, deliverables and the governance room — C10, C18, POR-08, POR-09, POR-15
status: approved
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-005, ADR-007, ADR-014, ADR-027, ADR-031, ADR-040, ADR-050, ADR-052, ADR-078, ADR-089, ADR-139, ADR-140, ADR-145, ADR-146, ADR-163, ADR-164, ADR-320]  # plan decisions P-16, P-25, P-29, P-42 in the body
related_specs: [SPEC-642, SPEC-644]
created: 2026-11-06
updated: 2026-11-06
---

> **Instructions for coding agents**
> - R-02's own SPEC (R-02-T01). The Given/When/Then text below is R-02 §3 verbatim
>   (`docs/plan/epics/R-02.md`); task rows are `docs/plan/epics/R-02.tasks.csv`.
> - Contracts provided: C10 `docs/contracts/deliverables.md` (R-02-T02) and C18
>   `docs/contracts/portal-approvals.md` (R-02-T03). Both start as 501 stubs.
> - Screen contracts: `docs/screens/POR-08.md`, `POR-09.md`, `POR-15.md`.
> - Agents never decide: every client decision action is denied to agent and system contexts at
>   the matrix, the live-human check and each provider's `CHECK (actor_kind = 'human')`.

## 1. Summary
R-02 gives a client's own people one place to decide what goes into their financial statements
(POR-08), one place to read and download what the firm delivers (POR-09) and, for those charged
with governance, a private room for the auditor's required letters (POR-15). Two contracts carry
it: **C10** publishes a deliverable once to named audiences with a download audit, and **C18** puts
any decision to the right client person and returns it to the module that owns it.

Sprint 29 builds the kickoff only: this SPEC, the screen contracts, the C10 and C18 stubs and
protected bundle 1 (R-02-T01 to T04). Services, screens and flags land S30 to S35.

## 2. Gate check (R-02 §0.1, at main 37856f6c7, 2026-11-06; DEC-2400)
"Accepted" below means decided in `docs/product/decision-log.md` or accepted in
`docs/adr/backlog.md`. The rows the solo rule decides with the plan's option are marked.

| Row | State on main | Bears on S29? |
|---|---|---|
| P-09 (ADR-146), P-13 (ADR-164), P-19 (ADR-320), P-11 (ADR-163), P-28 (ADR-148), P-06 (ADR-145), P-36 (ADR-139), P-39 (ADR-140), P-34 (ADR-138) | accepted | yes, all met |
| DEC-63, DEC-69, DEC-44, DEC-58, DEC-59, DEC-45, DEC-60, DEC-61, DEC-68 | decided | yes, all met |
| DEC-83, DEC-93 | row read "Proposed"; DEC-2400 takes the plan's option (log rule, AMENDMENT-solo) | yes, now decided |
| DF-03, DF-19, DF-28, DF-31, DF-40 | design facts carried in the epic and handoff; no log row | no: applied in T04, T14, T15, T19 |
| P-29 (ADR-151), P-14 (ADR-179), P-43 (ADR-159) | **proposed, not accepted** | no stub depends on them; **Ayush accepts** before the T05 migration and the window rules bind |
| P-16, P-25, P-42 | **ADR not drafted** (`to draft` in `docs/adr/backlog.md`) | no: needed by T11, T12, T19, T22 (S31 on) |
| P-56, DEC-54 | n/a, solo edition | no |

So T01 does not stop for the stubs. The three undrafted ADRs and three proposed ADRs stay open and
are named here so nothing treats them as met.

## 2.1 Open questions decided at kickoff (DEC-2400)
- **OQ-1 (decider rule):** the plan's recommendation. `proposed_entry`,
  `uncorrected_misstatements`, `fs_draft`: an owner grant **or** approver of record;
  `fs_package` for attest-flagged clients must also hold `ske_designee`. T03 encodes this in
  `DECIDER_RULES`, so a later change is one table.
- **OQ-4:** new template kind `approval_requested`, firm-editable database content.
- **OQ-8:** frozen C10 and C18 contracts, the migration, the serving code and the 501 stubs are the
  "contracts in production before Jan 1"; services merge dark in-window as new files.
- OQ-2, OQ-3, OQ-5, OQ-6, OQ-7 keep their later decide-by dates.

## 2.2 Contract issues
The row asks for GitHub issues; the solo edition has no second reader, so the issue text is this
section. C10 serves POR-09 a, a2, b, c, d, e, f and POR-15 e, A-06's drafts, A-07's release pack
and letters. C18 serves POR-08 a, a2, b, c, d, e, e2, f and POR-09 a2, b. Seed figures each must
carry unchanged: 48,600 = 33,540 + 15,060; 13,050 = 6,150 + 2,400 + 4,500; 22,250 = 35,300 − 13,050;
35,300 = 11,860 + 700 + 2,140 + 5,320 + 14,900 + 380; 16,500,000 = 14,895,000 + 1,605,000;
361,000 = 312,400 + 48,600; 16,861,000; 14,228,500 = 13,940,000 + 288,500.

## 3. Acceptance criteria (transcribed from R-02 §3)

AC numbers are the SPEC's (T01 transcribes them verbatim). **N's T20** writes the independent tests for AC-1…AC-37 (AY's amber code); **AY's T10** writes them for AC-38…AC-41 (N's red serving code, §3.15); N's **T08** holds the C10 and C18 provider contract suites. Invariants: **INV-1** the agent never decides · **INV-2** citations verified · **INV-3** walls hold · **INV-4** portal scopes isolated · **INV-5** audit attribution correct.

### 3.1 C18: one way to put a decision to a client (all kinds)

*As Hannah, I want every client decision — entries, statements, packages — to reach the right client person, be decided only by them, and come back to the module that owns it.*

- **AC-1** *Given* a module registers `engagements.register_client_approval_kind(kind, provider)` with `items()`, `item()`, `decide()` and `facts()`, *then* the portal lists only items whose provider reports `sent_to_client = true` for a scope the caller's grant covers; *given* an unregistered kind, *then* every route for it answers 409 `approval_kind_not_registered` and nothing is written (fail closed, chapter 03 §2.4).
- **AC-2 (decider rule)** *Given* a decision on any kind, *then* the caller must be a live client human (`identity.require_live_human` and `principal_kind = client`) holding, on the item's target scope, **an `owner` grant or the `approver_of_record` designation** (DEC-63); *and* where the client is attest-flagged (P-13) and the kind is `fs_package`, the decider must also hold `ske_designee`; the `proposed_entry` rule follows OQ-1 (default until answered: approver of record must also be SKE designee, the stricter reading of the POR-08 spec). A contributor, a third party (Sam Ortiz), a `tcwg`-only grant or a K-1 recipient gets 404 for items outside their scope and 403 `not_decider` inside it (INV-4).
- **AC-3 (MFA)** *Given* a decide or acknowledge call without a recent second factor, *then* 401 `mfa_recent_required` opens the existing step-up; the decision row records `mfa_verified_at` (P-09, DEC-34, R-29).
- **AC-4 (what you saw is what you decided)** *Given* every item detail carries `seen_hash` (the provider's content hash of amounts, lines, legend and highlights, or the deliverable version's `render_hash`), *when* a decide call's `seen_hash` differs from the current one, *then* 409 `item_changed` and the screen reloads with the new version; *given* the same `Idempotency-Key` twice, *then* one decision and the original response.
- **AC-5 (agent never decides)** *Given* an `AgentContext`, `SystemContext`, support session or any firm user, *then* every client decision action is denied at the matrix, the live-human check and each provider's `CHECK (actor_kind = 'human')`; banned-pattern rule **CLIENT-DECISION-001** names the only files that may call a provider's `decide()` (`modules/portal/approvals.py` and each provider's record-mode service) (INV-1, I-AGENT-NEVER).
- **AC-6 (attribution)** *Then* every provider receives `ClientDecisionContext(contact_id, user_id, grant_id, designation_basis, mfa_verified_at, channel='portal', ip, device, session_id)`, and ADM-07, AUD-16 and AUD-29 read "Dana Kowalski (client) · Sep 25" — never "via Agent" (INV-5, DEC-60).
- **AC-7 (pack rule)** *Then* no C18 DTO carries a field named or holding materiality, performance materiality, threshold, threshold-policy name ("BH AJE thresholds v2"), "Within threshold", review notes, sign-offs, agent, confidence or internal status; a schema scan over the portal OpenAPI fails the build if one appears.

### 3.2 Attest entries: accept, decline, ask (POR-08 e, e2)

*As Dana, I want to accept or decline each entry my auditor proposes before the plan records it, and ask about one first.*

- **AC-8** *Given* A-06 sent AJE-1, RJE-1, PAJE-1 and PAJE-2 to Dana (A-06-T10 approve-and-send), *when* she opens Approvals on Thu Sep 24 with the context picker "PY2025 audit ⇕", *then* the intro reads "Your auditor proposes these entries. Accepting means the plan records them in its 2025 financial statements." and four cards show the amounts, sub-lines and lines exactly as AUD-16 (48,600.00 = 33,540.00 + 15,060.00; 13,050.00 = 6,150.00 + 2,400.00 + 4,500.00), each with Accept · Decline… · Ask a question (**POR-08e**).
- **AC-9** *When* Dana accepts AJE-1, *then* `adjustments.api.apply_client_decision` records `client_approved` with her context and AUD-16 reads "Client approved · Dana Kowalski · Sep 25"; *when* she declines PAJE-1 with "Sponsor will correct under EPCRS in 2026", *then* the entry is `client_declined` (DF-28), the reason is sealed (Restricted, hostile content) and her card reads "Not recorded · Sep 25" with the reason (**POR-08e2**).
- **AC-10** *Then* no Post control exists anywhere for an attest client, and nothing is ever written to a client ledger (ADR-040, DEC-69); the posted-entries card never renders for an attest-flagged client.

### 3.3 Uncorrected misstatements acknowledgement (POR-08 e2)

*As Dana, I want to see what the entries I did not record would have done, and acknowledge it before I sign the representation letter.*

- **AC-11** *Given* every entry in the send batch is decided and at least one is `client_declined`, *then* the `uncorrected_misstatements` item appears with text built from code-computed figures: "If recorded, the two entries you chose not to record would increase net assets by $22,250.00 in total ($35,300.00 − $13,050.00). They'll be listed in your representation letter, where you confirm their effect is not material, individually and in total." The amounts come from A-06's frozen `sum_snapshots` row (iron curtain 22,250); the browser computes nothing (ADR-050).
- **AC-12** *When* Dana acknowledges, *then* one insert-only, human-only `uncorrected_misstatement_acknowledgements` row stores the snapshot ID, the net effect, `engine_version`, `inputs_hash` and her context, and `uncorrected_misstatements.acknowledged` is emitted for A-07's representation letter (AUD-21) and completion projector; *given* a newer SUM snapshot later, *then* a new item asks again and the old acknowledgement stays as history.

### 3.4 Package approval: approve, decline, ask (POR-08 a–d; fixture until C-02 / A-08)

*As Ben (approver of record), I want to check the six entries behind the August package, ask about one, and approve or decline the statements.*

- **AC-13** *Given* the `fs_package` kind is registered (C-02 or A-08), *then* Card A shows the parts, the highlights **verbatim as the partner approved them** (P-25; R-02 refuses to render highlights without an approving human), the legend line from the provider (AR-C 70 "Prepared by Brightwater Hale. No assurance is provided."), and Approve statements · Decline… · Ask a question (**POR-08a**); "Approve statements" opens the confirm (**a2**), and on confirm `closes.api.apply_package_decision` records the approval and the card reads "Approved by Tess Moreno · Sep 15, 8:42 AM" (**b**).
- **AC-14** *When* Ben chooses Decline…, *then* the O3 sheet requires one of `number_looks_wrong`, `something_missing`, `other` (note required for `other`, 1–1,000 characters), and the card reads "Declined · A number looks wrong" (**c**).
- **AC-15** *Given* a non-attest client, *then* Card B lists the posted entries read-only from C-02's posted-entries read with the right-hand pill "Posted · QBO 48213–48218", whole dollars in the list and cents in the lines table (11,860 + 700 + 2,140 + 5,320 + 14,900 + 380 = 35,300; 12,600 + 1,480 + 820 = 14,900), and the footer "Approved by Raj Malhotra and Priya Raman, Brightwater Hale · posted to QuickBooks Online Sep 14 (48213–48218)." — never "Within threshold" or a policy name (DF-19).
- **AC-16** *Given* the kind is not registered for the firm (all of S29–S35), *then* production shows neither Card A nor Card B; the fixture build renders a–d from scenarios and the parity harness locks them (DV-08).

### 3.5 C10: publish a deliverable once, to the right audiences

*As Margaret, I want the report pack to reach Dana and the committee the moment I release it, and to see when they open it.*

- **AC-17** *When* a provider calls `reporting.api.publish_deliverable(ctx, spec)` inside its own unit of work (A-07's ReleaseWorkflow under the EP's approval grant; A-06's send-draft; later C-02 and X-01), *then* one `deliverables` row per `(source_module, source_ref)` and one insert-only `deliverable_versions` row per evidence version are written with `deliverable_audiences` (e.g. the work item for management **and** the governance room for TCWG); a repeat call with the same source version is a no-op returning the same IDs.
- **AC-18** *Given* `is_draft = true`, *then* the version must reference a P-11 generated document whose render carries the DRAFT watermark; otherwise 422 `draft_without_watermark`. *Given* `restricted_use = true` (governance letters, SOC reports), *then* only the listed audiences can read it and the row reads "restricted use".
- **AC-19** *When* a newer version is published, *then* `deliverable_events` records `superseded` for the old one and the portal shows only the latest, with prior versions under "Earlier versions" for audience members; *when* the firm withdraws a version (OQ-7), *then* `withdrawn` is recorded with a reason and the row reads "Replaced by Brightwater Hale · ‹date›".
- **AC-20** *Then* `deliverables_for_work_item` gives AUD-24's dock and CLS-08 the delivery state per audience contact ("Delivered", "Viewed Oct 9, 10:22 AM", "Downloaded") from `deliverable_receipts`.

### 3.6 Draft review and management approval (POR-09 a, a2, b)

*As Dana, I want to read the draft, comment on the line I'm unsure about, and approve the statements once the answer is in.*

- **AC-21** *Given* A-06 sent draft v3 (`fs_draft`), *then* POR-09 shows the band "PY2025 plan audit" with "Financial statements and supplemental schedules · Draft v3 · 14 pages · Oct 6" amber "For your review", "Representation letter · Sign on Oct 9 (report date)" neutral "In Sign" (from C7) and "Engagement letter · Signed Jun 2026" green-tint "Signed"; Coming next lists "Independent auditor's report · At release · expected Oct 9" and "Form 5500 · Filed by you with Summit Plan Administrators · due Oct 15 (extended)" from C1 milestones (**POR-09a**).
- **AC-22** *Then* page images are served by the server with the watermark burned in; page 2 foots 14,895,000 + 1,605,000 = 16,500,000; 312,400 + 48,600 = 361,000; 16,861,000 (2024: 13,940,000 + 288,500 = 14,228,500); the client never receives an unwatermarked draft byte.
- **AC-23** *Given* draft v3 while v4 exists, *then* Approve statements… is disabled with "A newer draft is available"; *on* draft v4 (Thu Oct 8), *when* Dana confirms, *then* `reporting.api.apply_management_decision` writes the human-only `statement_approvals` row (A-06), `fs.approved_by_management` is emitted, AUD-19's item ticks, and POR-09 reads "Approved by you · Oct 8" with "Brightwater Hale will release the final statements with the report." while the watermark stays (**a2 → b**).

### 3.7 Finals, downloads and the download audit (POR-09 c)

- **AC-24** *Given* A-07's release on Fri Oct 9 publishes the pack, *then* the rail shows "Independent auditor's report.pdf · 3 pages" and "Financial statements and supplemental schedules.pdf · 14 pages · final", both green "Final", pages without watermark and a primary Download (**POR-09c**).
- **AC-25 (download audit, amber half)** *When* Dana downloads, *then* the BFF checks the audience through `reporting.api`, asks `evidence.api.issue_deliverable_download` for the URL (§3.15), writes the `deliverable.downloaded` audit event and updates `deliverable_receipts` in the same unit of work, and AUD-24's dock reads "Downloaded · Oct 9". The URL never appears in a notification, email or log line.

### 3.8 My K-1s and role union (POR-09 d)

- **AC-26** *Given* Meera Shah holds `taxpayer` on her 1040 and `k1_recipient` on Ridgeline's package, *then* POR-09 shows "2025 Tax Return · Not ready yet · we're preparing it" and the "My K-1s" band with "Ridgeline Property Partners, LP — 2025 Schedule K-1 (Form 1065)" green-tint "Released Sep 15"; the summary card reads Box 2 468,008 · Box 5 6,992 · Box 18A 2,356 · Box 19A 228,000 · Ownership "38% · full year"; "Schedule K-3 · Included — Ridgeline has no foreign activity; all income is U.S. source"; "We've also added this K-1 to your own 2025 return." Attachment chips use T-02's existing `/v1/portal/k1s/{pid}/attachments/{doc_id}` route (its electronic-furnishing consent sheet, T-02 DV-12, appears first), so K-1 Viewed/Downloaded stays in T-02's tracking. A draft K-1, another partner's K-1 and the partnership return never appear (INV-4).

### 3.9 Governance letters and acknowledgements (POR-15 a, b, d, f)

*As Victoria, I want to read what our auditor must tell the committee, confirm I've read it, and keep the committee's business apart from management's.*

- **AC-27** *Given* A-07 (Margaret, fresh MFA) sends the planning letter to the Benefits Committee's room, *then* `tcwg` grants exist for Victoria Lam (chair), Robert Haines and Dana Kowalski on the `governance_room` scope (issued by R-02 from A-07's recipients through invitations v2), each member gets the **Governance letter** email from the firm's database template, and POR-15 shows the rail "Benefits Committee · Northwind Robotics 401(k) Plan · 2025 audit" with the planning letter amber "New", the completion letter "Not yet", the internal-control letter "Not yet", and the Committee band with each member's state (**POR-15a**).
- **AC-28** *Then* the paper card renders the approved letter version's text — A-07's sections without citation markers, letterhead, date "September 17, 2026", signature "Margaret Okonkwo · Engagement Partner" — and refuses any version without an EP send row; *when* Victoria acknowledges, *then* `assurance.api.record_acknowledgement` writes one row (idempotent per member and version), and the rail reads "Acknowledged by the committee · Sep 21" once all three have; AUD-22 shows "Acknowledged Sep 21 · Benefits Committee" (**b**). *Given* Dana's management grant (owner/plan administrator), *then* every governance route answers 404; under her `tcwg` grant she reads the letters (DEC-93: privacy per role and per scope). *Given* the AU-C 265/703 letter sent Nov 20, *then* d shows the significant deficiency (the Dec 26, 2025 payroll of $48,600 remitted Jan 9, 2026), the other deficiencies, the AU-C 703 reportable findings and the restricted-use paragraph, due Dec 8 (**d**, CST clock). Before any letter, f shows "Nothing from your auditor yet." / "Planning communications usually arrive before fieldwork."

### 3.10 Private inquiries (POR-15 c)

- **AC-29** *Given* A-04 sent two AU-C 240 inquiries to Victoria through T-02's questionnaire service with her contact as addressee and the room as scope, *then* "Questions for you · 2" lists them with long answers (96 h) and the note "Your answers go only to the Brightwater Hale audit team. Other committee members and plan management can't see them."; Send answers submits through T-02's addressee-only submit; Robert Haines and Dana (either grant) get 404 for her questionnaire and its answers (INV-4).

### 3.11 Reports in the governance room (POR-15 e)

- **AC-30** *Given* A-07's release published the pack with the room among its audiences, *then* Reports lists "Independent auditor's report" and "Financial statements and supplemental schedules" (final, 14 pages) with Download (audited as AC-25); a deliverable whose audiences exclude the room never appears, and nothing from management's request list does (**POR-15e**).

### 3.12 Questions and page comments (POR-08 d and e, POR-09 a, POR-15 "Ask the auditor…")

*As Ben, I want to ask about one entry without leaving Approvals; as Dana, I want to point at a line on the draft.*

Questions and comments are **client routes over P-05's collaboration API** (P-05 denies client roles on its own routes). R-02 registers three anchor kinds with `collaboration.register_anchor`: `client_approval_item` (portal), `deliverable_version` (portal; locator `{page, line_ref}` or `{page, x, y}`; only when the version has `page_comments = true`) and `governance_communication` (assurance; **author-only client readers**, an additive `client_reader_policy` hook requested from P-05).

- **AC-31** *When* Ben chooses "Ask about this entry", *then* an inline O3 composer opens prefilled "About: Accrued expenses $14,900.00 (August 2026)"; sending writes a client-authored comment on the item's thread, the row reads "Question sent Sep 14", and the item's team gets `client_question_asked`; the firm replies from the anchor's thread, shared through `communications.api.check_scope` (**POR-08d**; POR-07 and INB-04 link it later, N-03, DV-01).
- **AC-32** *When* Dana clicks page 2 beside "Notes receivable from participants", *then* pin 1 drops and the comment field opens; sending writes a client-authored thread comment and a `statement_approvals` "commented" row through `reporting.api.apply_management_decision(kind='comment')`, so it lands in AUD-20's client-comments list; selecting the comment lights its line with `--match-bg #ECD9F0` / `--match-line #BF99C8` (E1 MatchProvider) only while selected; a version with `page_comments = false` offers no pin (**POR-09a**).
- **AC-33** *When* Victoria uses "Ask the auditor…", *then* the thread is readable by her and by the engagement's EP and manager only — not by Robert Haines, not by Dana under either grant — and `tcwg_question_asked` notifies Margaret and Hannah.
- **AC-34** *Then* every client string (reasons, notes, comments, questions, answers) is treated as hostile (ADR-052): sealed, 1–1,000 or 1–4,000 characters as the field defines, never rendered as HTML, never stored in an audit or notification row, and tagged `content_origin = client`.

### 3.13 Home, nav and notifications

- **AC-35 (Home and nav)** *Given* the flags on for the firm, *then* `modules/portal/home_sources/approvals.py` ("4 entries to review") and `deliverables.py` ("2 documents ready") feed P-08's home read model and the counts tie to the list routes; the Approvals count ("1") and the governance reduced nav (Communications · Reports · Questions for you with count) come from `/v1/me.portal`; the bottom tab bar's More sheet holds Approvals and Deliverables (DEC-45). *Given* a flag off, *then* its source returns nothing and its nav item is absent. There is **no portal bell** (DEC-58 d).
- **AC-36 (client email)** *Then* emails carry no amounts and no account numbers, one dark call to action and the firm's sender domain: `approval_requested` *(new template kind)* on a provider's `client_approval.requested`; "Deliverable ready" (existing POR-20 template) on `deliverable.published` for a non-draft version with no approval item; `governance_letter_sent` *(DF-40)* on `governance_communication.sent`. The texts are database content loaded through ADM-10 import; a missing template blocks that email (fail closed, logged) while the item still shows on Home.

### 3.14 Mobile, flag-off and other non-artboard states

- **AC-37** *Given* a 390-wide viewport (DF-03, structural), *then* POR-08 becomes the bento-close-control card with six olive rows, one ring row "August financial statements · Review required" and a dark full-width 44-h "Review" that opens the package as a full-screen sheet; POR-09 lists by work item, opens a page full width with a floating pin, puts comments in a bottom sheet and keeps a sticky Approve; POR-15 shows a Communications list card, the letter full width with a sticky 44-h Acknowledge, and Questions for you as a second segmented tab. *Given* a flag off, *then* the designed C-20 flag-off state renders (never a 404 page); loading shows skeletons after 200 ms; refusals use the domain message map ("Only the owner or approver of record can approve this.").

### 3.15 Serving pages and files (red, T07; tests by AY in T10)

- **AC-38** *Given* a deliverable version and a principal whose grant covers one of its audiences (checked through `reporting.api`), *then* `evidence.api.deliverable_page` returns the stored page image; for a draft the DRAFT watermark is present on every page (P-11 AC2.2), and no code path returns an unwatermarked draft byte.
- **AC-39** *Then* `evidence.api.issue_deliverable_download` returns a URL bound to the tenant's bucket prefix and the object version, valid 60 seconds, with `Content-Disposition: attachment` and the deliverable's title as filename; a replay after expiry fails.
- **AC-40** *Then* every page image and every URL issue writes one `access_events` row (tenant, contact, deliverable version, kind `page_view` or `download`, request ID); TRI-classed deliverables (K-1s and tax deliverables, C19) are marked as such in the row.
- **AC-41** *Given* a walled firm user, a client outside every audience (Sam Ortiz; Dana's management grant for a governance letter) or another tenant, *then* 404 with no count and no timing difference beyond tolerance; *given* `access.changed` for the caller, *then* in-flight URLs are not reissued.

### 3.16 The window and the live path

| When | What merges | Rule (P-29, chapter 01 §1.2.4) |
|---|---|---|
| S29–S30, by the **Thu Dec 23, 2027** train | C10 and C18 stubs (T02, T03), protected bundle 1 (T04), the migration (T05), the shell hooks (T06), the red serving code and adjustments line (T07), the contract suites (T08) | "Contracts in production before Jan 1": deliverables (C10) and approvals (C18), read by R-02 as frozen contracts, the migration, the red serving code and the 501 stubs in production, with the C10 and C18 services merging dark in-window as new files (S31–S32) behind those routes. Chapter 01 §1.2.4 does not say which reading it means, so R-02 records it as a chapter 01 clarification through the decision log (OQ-8) rather than assuming it. The hooks change nothing in production: manifest entries stay `planned`, nav is server-computed and the home sources do not exist yet |
| S31–S32 | Services T09, T11 and T12 (and T13's seed slices) as libraries with service-level tests | Routes still answer 501 (no flag needed); no live-path code is touched; any migration is expand-only and pipeline-run after 8 pm CT |
| **Tue Jan 25, 2028** train | Protected bundle 2 (T14): flags created (expire Apr 24), routes wired behind them | New modules merge dark behind default-off flags |
| S33–S35 | T15 and T16 behind the flags, then frontends, threads, journeys, parity | New route modules and flag-gated home sources only; the live P-08 shell and R-01 screens are not edited |
| **Tue Feb 29, 2028** 7 pm CT | Canary flip of all three flags | e2e green on staging, a one-week canary shadow, written rollback, both approvals |
| **Tue Mar 7, 2028** (S36) | Real-firm flip of `portal.approvals` and `portal.deliverables` for firms on Dec-YE audits | Same four conditions plus the pen-test delta closed (T18); otherwise A-06 record mode continues |
| **Tue Mar 21, 2028** (M16) | `portal.governance_room` with the release and archive flip; POR-09 "Final" follows A-07's per-firm flip | Or Tue Apr 25 after the window; no promotion in the Mar 13–17 deadline week |

## 4. Out of scope in Sprint 29
Services T09, T11, T12; serving code T07; migration T05; flags T14; screens T15 to T21. Every route
answers 501 until its task.
