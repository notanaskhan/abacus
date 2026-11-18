---
id: SPEC-711
title: Q-05 Quality management and records governance — AUD-28, AUD-30, ADM-11, ADM-12, FIL-02
status: approved
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-016, ADR-024, ADR-026, ADR-032, ADR-033, ADR-034, ADR-050, ADR-066, ADR-078, ADR-104, ADR-148, ADR-151, ADR-159, ADR-161, ADR-167, ADR-179, ADR-186, ADR-320]
related_specs: [SPEC-341, SPEC-710]
created: 2026-11-18
updated: 2026-11-18
epic: Q-05
task: Q-05-T01 (TASK-8608)
---

# SPEC-711 · Quality management and records governance

> **Instructions for coding agents**
> - The design is `docs/plan/epics/Q-05.md` §1 to §8; task rows `docs/plan/epics/Q-05.tasks.csv`.
>   §3's stories and acceptance criteria are adopted verbatim; this file numbers their testable
>   cores AC-1 to AC-36 and records the gate check and the open-question answers.
> - Screen contracts: `docs/screens/{AUD-28,AUD-30,ADM-11,ADM-12,FIL-02}.md` (35 artboards).
>   Module contracts: `docs/contracts/quality-management.md`, `docs/contracts/records-governance.md`
>   and the post-issuance section of `docs/contracts/audit-completion.md`.
> - The agent never decides, concludes, evaluates, approves, destroys or places a hold (INV-1).
>   Every count, rate, comparison and score is code (ADR-050). Walls are 404 with no count (DEC-43).
> - S50–S51 merge dark only (P-29): default-off flags, expand-only migrations, no live-path change
>   before the Tue Oct 24, 2028 train.

## 1. Summary
Margaret runs the firm's SQMS No. 1 from ADM-11 and ADM-12: objectives at risk, QM findings, the
agent override rate and draft-vs-final accuracy from one projection (DEC-96), inspections with
objective inspectors and time-boxed grants, and the annual evaluation on a card reserved to her.
Consultations live on a firm log with differences of opinion resolved before release (AUD-28).
Post-issuance cases on locked archives are evaluated by code and decided by the EP, with
additions, never edits (AUD-30). Felix keeps retention at or above the legal minimum, places and
releases holds, and destroys eligible records in dual-approved batches with a certificate (FIL-02).

## 2. Gate check (main 1ca51eec9, 2026-11-18; DEC-5608)

| Decision (Q-05 §0.1) | On main | State | Q-05 use |
|---|---|---|---|
| DEC-71 / P-14 retention, holds, destruction | ADR-179 | accepted | retention per record type × service line; reference-counted holds; dual-approved destruction |
| OQ-1 / OQ-3 amendment to P-14 | — | drafted in Q-05-T32 (this sprint) | gates T14 and T15 only (S52) |
| P-43 archive seal, immutability, Object Lock | ADR-159 | **proposed** | Q-05 uses only what A-07 built on main (the `post_issuance` and `destruction_tombstone` exception kinds, A-07-T13); acceptance recorded as an S50 follow-up (AMENDMENT-solo: decide and carry on) |
| DEC-83 audit completion | A-07 (`audit-completion.md`) | decided | EP-reserved cards; the full consultations log here |
| DEC-96 Insights metric definitions | chapter 09 | decided | one override projection shared by ADM-11 and INS-02 |
| DEC-50 / P-49 autonomy policy | ADR-186 | accepted | the published policy's 8% tolerance and 25-output sample |
| DEC-21 / P-10 roles | `_roles.yaml` | decided | `quality_partner`, `security_admin`, `specialist`, `eqr_reviewer` |
| DEC-36 / P-07, DEC-24 / P-35 | ADR-134, ADR-161 | accepted | decision cards, human gates, single-use grants |
| DEC-55 / P-28 flags vs entitlements | ADR-148 | accepted | four flags retire into `quality_management` |
| P-19 deterministic documents | ADR-320 | accepted | the destruction certificate |

## 3. Open questions (Q-05 §11.2; recommended answers; DEC-5608)
OQ-1 version deletion on primary and replica through a destruction-only role, tombstones,
derived-store purge, certificate with the 35-day backup statement (amendment in T32) · OQ-2 exclude
records still under a storage lock; FIL-01 shows "Retained until ‹date› (storage lock)" · OQ-3
`synthetic_min_retention_days = 1` for synthetic tenants outside production only · OQ-4
`quality_partner`, `practice_leader` in scope and the Monitoring reviewers group read ADM-11/12;
not `firm_admin` · OQ-5 firm-scope decision cards with `qm_ultimate` · OQ-6 explicit time-boxed
inspector grants · OQ-7 no agent-drafted evaluation memo in v1 · OQ-8 an unresolved difference of
opinion blocks release (per firm after Oct 20) · OQ-9 live after the Bedrock suite and a clearance
record · OQ-10 certificate: batch, scope, counts, approvers, hold re-check, exclusions, manifest
hash, checkpoint root, backup statement; 7 years · OQ-11 "+ New policy" creates a service-line
override at or above the type's policy; the register loads by import · OQ-12 batch cancellation by
API and runbook only · OQ-13 "quality management documentation" joins C21's retention minimums as
database content after counsel confirms.

## 4. Acceptance criteria

### Quality dashboard and agents (ADM-11)
- **AC-1** Sep 14, 2026: 2 of 24 objectives at risk, 5 open QM findings, 6.0% override
  (206 of 3,410), 96.8% accuracy, 2 open consultations, 92 days to Dec 15.
- **AC-2** Denver recomputes to 61 of 1,128 (5.4%); objectives stay firm-wide.
- **AC-3** EBP Audit Workpapers expands to 37 = 21 + 9 + 7; agents above tolerance are raised as
  QM findings by the nightly job as the system actor, never by the agent.
- **AC-4** The accuracy drawer reads 1,320 of 41,260 fields (1 − 1,320 ÷ 41,260 = 96.8%).
- **AC-5** Laura Kemp (Monitoring reviewer) reads ADM-11 read-only; a firm admin does not (OQ-4).

### Monitoring and inspections (ADM-12)
- **AC-6** Tiles read 2 Planned · 1 In progress · 3 Concluded · 5 Findings open; six inspections.
- **AC-7** An inspector who is the EP, EQR or a team member of the inspected engagement is refused
  ("Thomas Whitcombe — EP on Sterling Freight ✕ cannot inspect"); the trigger refuses it too.
- **AC-8** Each inspector gets a time-boxed read-only grant to the archive and its activity log.
- **AC-9** Only the QM owner evaluates a QM finding; the evaluation is insert-only and human-only.
- **AC-10** The annual evaluation is decided on a firm-scope card reserved to the individual with
  ultimate responsibility ("Concluded Dec 14, 2026 · Margaret Okonkwo").

### Consultations (AUD-28)
- **AC-11** The firm log reads Open 2 + Concluded 3; walls leave no row and no count.
- **AC-12** Only the consulted person records the conclusion and the implemented flag.
- **AC-13** A difference of opinion is resolved by the QM owner; unresolved, it blocks release.
- **AC-14** Filtering by engagement from AUD-19 or AUD-18 shows only that engagement's rows.

### Post-issuance (AUD-30)
- **AC-15** PI-01 compares (12,250) on three lines against clearly trivial 12,610 and 4.9% of
  252,200, computed by code.
- **AC-16** The agent's analysis ends "I have not decided whether this needs action."; reserved
  actions never appear on agent output.
- **AC-17** The EP decides No action, Reissue or Notify; No action adds an EP-approved archive
  addition with its own hash; nothing in the locked archive is edited or deleted.
- **AC-18** Reissue opens AUD-23 g (dual-dated) through A-07's release path only.

### Records governance (FIL-02)
- **AC-19** Eight record types show the legal minimum beside the firm policy; a policy below the
  minimum is refused; audit documentation is locked.
- **AC-20** Policy versions are insert-only with text and an effective date.
- **AC-21** Holds are placed by partners, `security_admin` and `firm_admin` at client, year, work
  item or folder scope; reference-counted; the reason maps onto Q-02's codes.
- **AC-22** Batch 2026-Q3 lists 1,204 documents of 31 former clients; two approvals in distinct
  roles (a second approval by the same person or role is refused).
- **AC-23** Approval needs the typed confirmation `DESTROY 2026-Q3` and fresh MFA.
- **AC-24** A per-item hold re-check excludes held items (fil02e: 3 excluded, 1,201 destroyed).
- **AC-25** Destroyed documents answer 410 "Destroyed under DC-2026-Q3"; tombstones never revert.
- **AC-26** The certificate renders byte-identically (C11) and is kept 7 years.
- **AC-27** The `destruction_execute` control stops execution between items.
- **AC-28** Samuel Ito reads FIL-02 read-only; Daniel Reyes is notified of the Whitley hold.

### Platform and invariants
- **AC-29** Four flags (`quality.management`, `audit.consultations_log`, `audit.post_issuance`,
  `records.governance`) exist default off.
- **AC-30** The agent is denied every decide, conclude, evaluate, approve, destroy and hold action;
  generated tests prove each denial.
- **AC-31** Migrations are expand-only with forced RLS; insert-only and human-only CHECKs hold.
- **AC-32** Q-02's tables are extended, never redefined (retention policy versions, legal holds).
- **AC-33** Stubs answer 501 under one action each; the api-client regenerates.
- **AC-34** Seed slice foots every golden figure of §5.3 at its snapshot.
- **AC-35** Audit payloads carry identifiers only (DEC-60).
- **AC-36** No 14th nav item (D4); no peer comparison (D6).

## 5. Task map (S50)
T01 this file, the contracts and skeletons · T02 protected bundle (AC-29, AC-30) · T03 stubs (AC-33)
· T05 migration practice_quality · T06 migration records_destruction (AC-31, AC-32) · T04 seed
slice (AC-34) · T32 P-14 amendment (draft; counsel acknowledgement is human). Services, screens and
journeys land S51–S54 per the epic.
