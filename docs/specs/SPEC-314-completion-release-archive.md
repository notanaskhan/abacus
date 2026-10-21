---
id: SPEC-314
title: "Completion, release and archive, first slice (record mode): EQR concurrence over a code-built digest (G6), going concern, report record and approval, representation letter dated the report date (G7), partner release (G8), sealed archive lock (G9)"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-140]
related_specs: [SPEC-300, SPEC-301, SPEC-311, SPEC-313]
created: 2026-10-21
updated: 2026-10-21
---

## 1. Summary
This is A-07 in record mode. The firm drafts the report and the representation letter in its own tools, and the final documents are evidence versions on the engagement. Abacus records, checks, gates and seals.

- Every decision is a named person's act.
- Code builds the EQR digest, every gate fact and the seal.
- No model is called.

The report builder, letter templates, governance communications, e-signature envelopes, clocks, workflows, database immutability triggers, post-lock additions and fresh MFA are later A-07 tasks.

Migration 0077 adds four tables, all insert-only with a human-only CHECK: `eqr_concurrences`, `completion_records`, `releases` (one per engagement) and `archives` (one per engagement).

## 2. Acceptance criteria
- **AC-1 Read.** `GET /v1/engagements/{id}/completion` (`completion.read`) returns:
  - the checklist: G1, G2, G3, G5, G6 (or not required), going concern, report approved, G7, G8 and G9;
  - the EQR digest;
  - the records;
  - what blocks release and the lock.
- **AC-2 G6.**
  - The digest is built by code from `engagements.judgments_of`. Fieldwork registers materiality and its decision, significant risks and their approval, and the uncorrected misstatements against materiality.
  - Only an EQR on the team (`reviewer`) concurs, attesting they weren't involved in performing the engagement (CHECK). Concurrence is refused while review notes are open.
  - G6 is met when the newest concurrence is over the current digest. A changed judgment gives `eqr_digest_changed`.
  - With no EQR on the team, G6 isn't required.
- **AC-3 Going concern.** The partner decides (`completion.decide`): no substantial doubt, doubt alleviated, or doubt exists. The last two need a basis.
- **AC-4 Report.**
  - The report is recorded with its opinion form, the going-concern paragraph flag (required when doubt exists), the report date and the document.
  - The partner approves the newest record (`report.approve`). A newer record needs approval again.
- **AC-5 G7.** The signed representation letter (document and date) must be dated the report date.
- **AC-6 G8.**
  - The partner releases, attesting (`report.release`).
  - In the same unit, the server re-checks G5, G6, G7, going concern and the approved report, and refuses with what blocks.
  - It records the release with the gate facts, sets documentation completion to the report date + 60 days, and sets the assurance phase to released.
  - After release, completion records can't change.
- **AC-7 G9.**
  - After release, with review still complete, a manager or the partner locks, attesting assembly is complete (`archive.lock`).
  - The seal is a SHA-256 Merkle root over sorted leaves: every reviewable's content hash, every recorded document's fingerprint, the concurrence and the release. The manifest lists the leaves.
  - The phase becomes archived, the work items record the lock, and the engagement status becomes archived, which `authorise` makes read-only (AUTHZ-003).
- **AC-8 Who.** Release and going concern are the engagement partner's; the lock is a manager's or the partner's; concurrence is the EQR's. The agent is denied every action.
- **AC-9 Web.** A "Completion" tab shows:
  - the checklist;
  - the EQR card (digest, concurrence state, and the concur control for the EQR);
  - going concern, report and representation-letter cards, with documents chosen from the engagement's evidence;
  - release (blockers in fixed words, and the attestation);
  - the archive (blockers, the attestation, and the seal once locked).
