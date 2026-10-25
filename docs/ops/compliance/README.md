# Compliance programme and gate tracker (Q-02-T01)

One page that says what must be true on **M4 (Fri Dec 11, 2026)** and **M7 (Fri Apr 16, 2027)**, who owns each item, and by when. Chapter 01 §1.2.2 sets the criteria; Q-02 §10 sets the evidence. The control map is [`../soc2-control-map.md`](../soc2-control-map.md); the vendor and assurance tracker is [`../vendors/README.md`](../vendors/README.md).

## Rules

1. **No exception path.** A criterion is met with evidence or it is not met. Nothing is waived, deferred past its gate, or passed "with a note". When an item is late, the gate date moves (the plan's one pre-agreed fallback is M7 on Fri May 14, 2027 if the SOC 2 Type I report is late; it moves shadow to Tue Jun 15 and R3 to Tue Jul 27). The criterion itself never changes.
2. **Owner** is the builder, or the external party that acts (counsel, the SOC 2 auditor, the pen tester). Where an external party acts, the builder still owns chasing it. The solo amendment (`docs/plan/AMENDMENT-solo.md`) replaces every founder role.
3. **Status words:** `open`, `in progress`, `met`, `late`. Only `met` counts, and only when the Evidence column names where the evidence is.
4. **Never in git:** prices, amounts, contract or DPA text, the names of the auditor, pen-test firm, counsel, insurers or design partners, counsel's advice, reports under NDA, account IDs, keys, secrets. The repository is public. Put the item in the document vault and write only its opaque reference (for example `V-012`) in a row.
5. Evidence is dated on or before the gate day. Evidence in the compliance tool is cited by control, never copied here.

## Qualified Individual designation (AC-3)

| Item | Record |
|---|---|
| Designated Qualified Individual (FTC Safeguards Rule, 16 CFR 314.4(a)) | The builder, as the single designated person. The lead-and-deputy pairing in the epic collapses under the solo amendment. |
| Designated on | Tue Oct 20, 2026 (this file) |
| Written scope | Oversees and enforces the information-security programme: the WISP (Q-02-T40), this tracker, the control map, the AI threat model, incident response, and the periodic report on the programme. With no one above the builder, the report is a dated entry in the compliance tool. |
| Risk of one person | Single point of failure and no second reviewer. Compensating controls are under Open items and in ADR-100. |
| Queued issue | The `soc2-risk` issue is created by F-01-T01 (the history secret-scan record: commit range, tools, counts, decisions, never values). It is imported into the compliance tool when Q-02-T10 connects it. This task adds no issue of its own. State: **queued, not yet verified to exist**; verify when F-01-T01 closes. |

## M4 gate: Fri Dec 11, 2026 (production stood up, controls operating)

Criteria from chapter 01 §1.2.2 (M4), Q-02 §10 items 2 and 3, and §3.13 (AC-46). Dates are due dates; an earlier working date is given where the plan names one.

| # | Criterion | Owner | Date | Evidence | Status |
|---|---|---|---|---|---|
| M4-01 | Production AWS account with the synthetic canary tenant only, no real data (R1) | builder | Fri Dec 11, 2026 | Q-01 epic; canary run history | open |
| M4-02 | SLO alarms live as code with burn-rate alerts, each alert linked to an SLO or ticket-only (ADR-093) | builder | Fri Dec 11, 2026 | [`../slos.md`](../slos.md); alarm definitions in `infra/` | open |
| M4-03 | Status page live | builder | Fri Dec 11, 2026 | Status page address recorded in the vault | open |
| M4-04 | Paging reaches the builder; one test page acknowledged (ADR-100) | builder | Fri Dec 11, 2026 | Paging tool test record | open |
| M4-05 | First restore drill completed, with control totals and evidence fingerprints verified (RB-10, RB-15; ADR-096) | builder | Fri Dec 11, 2026 | Drill record in the compliance tool; rehearsal date in [`../../runbooks/README.md`](../../runbooks/README.md) | open |
| M4-06 | Compliance tool chosen and connected to every AWS account, the GitHub organisation, the identity provider, the email workspace and the HR roster; device agent on the builder's laptop; control owners assigned (Q-02-T10) | builder | Choose by Fri Oct 30; connect by Fri Nov 27, 2026 | Tool shows every integration connected and the device compliant | open |
| M4-07 | First quarterly access review done (`make access-review QUARTER=2026Q4`) | builder | Fri Dec 11, 2026 | Review record in the tool | open |
| M4-08 | Incident-response tabletop held (RB-08, suspected cross-firm exposure) | builder | Fri Dec 11, 2026 | Tabletop write-up in the tool | open |
| M4-09 | Security training completed | builder | Fri Dec 11, 2026 | Training record in the tool | open |
| M4-10 | Risk assessment completed, including the AI threat model and the exposure of a public repository | builder | Fri Dec 11, 2026 | Assessment in the tool; [`../../architecture/ai-threat-model.md`](../../architecture/ai-threat-model.md) | open |
| M4-11 | SOC 2 auditor engagement letter signed; the auditor is not a design-partner firm; booked early because auditors are busy in their own January to April season | builder, auditor | Fri Dec 11, 2026 | Vault reference only; no name here | open |
| M4-12 | Pen test booked for Mon Feb 15 to Fri Mar 5, 2027 on a build pinned Fri Feb 12 | builder, pen tester | Fri Dec 11, 2026 | Vault reference only | open |
| M4-13 | `security` CI stage (generated tenant isolation, permission matrix and route introspection tests; CodeQL; dependency review; pip-audit; Trivy) is a required check on `main` (AC-46; Q-02-T13, Q-02-T15) | builder | Fri Dec 11, 2026 | Ruleset export; green run on `main` | open |
| M4-14 | Control evidence uploaded and dated on or before Fri Dec 11 for every control marked `M4` in the control map (Q-02-T19) | builder | Fri Dec 11, 2026 | Compliance tool, control by control | open |
| M4-15 | Feature flags expiring in the Dec 14 to Dec 18 window renewed (the plan's nine renewals; ADR-089, ADR-151) | builder | Fri Dec 18, 2026 | `docs/architecture/feature-flags.yaml` | open |

Linked, owned by the F-09 tracker: the SQMS 1 Technology Resource Pack sent to prospects by Tue Dec 15, 2026.

## M7 gate: Fri Apr 16, 2027 (real-data gate, R2)

Criteria from chapter 01 §1.2.2 (M7) and Q-02 §10 items 1, 3, 5 and 6. The dossier `docs/ops/gates/M7-real-data-gate.md` (created by Q-02-T49) links the evidence for every row and carries the builder's signature on the gate day.

| # | Criterion | Owner | Date | Evidence | Status |
|---|---|---|---|---|---|
| M7-01 | SOC 2 Type I report in hand, as of Mon Mar 1, 2027 (report expected about Fri Apr 2; confirm the auditor's timing) | auditor, builder | Report by Fri Apr 2; gate Fri Apr 16, 2027 | Report in the vault; reference in the dossier | open |
| M7-02 | Type I readiness gaps closed | builder | Fri Feb 26, 2027 | Readiness assessment in the tool; gap register [`type-1-readiness.md`](type-1-readiness.md) (Q-02-T35) | in progress |
| M7-03 | Pen test #1 done; every critical and high retested closed; attestation letter received | pen tester, builder | Retest closed by Fri Apr 9, 2027 | Letter in the vault; finding tickets closed; readiness [`../gates/pen-test-1-readiness.md`](../gates/pen-test-1-readiness.md), environment [`../pentests/2027-02-environment.md`](../pentests/2027-02-environment.md) | open |
| M7-04 | Provider-terms register holds a current Bedrock entry with counsel as second approver; `review_by` at least 90 days after Tue Jun 1, 2027 (ADR-114, ADR-115) | counsel, builder | Fri Apr 9, 2027 | `docs/operations/provider-terms.yaml`; Q-02-T18 | open |
| M7-05 | Per-agent Bedrock evaluations pass for every agent that will touch real data (screener, upload reviewer, matcher), including shadow-stage runs; no threshold lowered; route-parity report under 90 days old on Jun 1 | builder | Reports committed by Fri Apr 9, 2027 | `docs/operations/`; `evals/baselines.yaml`; Q-02-T44 | open |
| M7-06 | Firm opt-in (SPEC-036) recorded per firm before its first agent run; exclusion and agent stages live | builder | Fri Apr 16, 2027 | Q-02-T07, Q-02-T08; tests from Q-02-T09 | open |
| M7-07 | MSA and DPA ready to sign, with the sub-processor list generated from the register | counsel, builder | Fri Apr 16, 2027 | Vault reference; F-09 tracker | open |
| M7-08 | Cyber and technology E&O insurance bound | builder | Fri Apr 16, 2027 | Certificate in the vault; F-09 tracker | open |
| M7-09 | WISP approved by the Qualified Individual (Q-02-T40) | builder | Fri Apr 9, 2027 | [`wisp.md`](wisp.md) (v1 draft 2026-10-25); approval dated in its §10 | in progress |
| M7-10 | MFA enforced for staff, and for portal owners and signers (Q-02-T37) | builder | Fri Apr 16, 2027 | `make mfa-report` output | open |
| M7-11 | Restore drill within the quarter; the Q1 drill includes `make audit-chain-verify` on the restored copy | builder | Fri Mar 26, 2027 | Drill record (Q-03-T053) | open |
| M7-12 | Compliance kernel complete: hash chain, access events, actor kinds, retention floors, legal holds, dual-approval firm export, incident register with the FTC clock | builder | Fri Apr 16, 2027 | `docs/contracts/compliance-kernel.md`; Q-02-T14 to Q-02-T50 | open |
| M7-13 | Seven consecutive green nightly audit-chain verifications on staging and on the production canary | builder | Fri Apr 16, 2027 | Nightly run history | open |
| M7-14 | Real-data rehearsal system test passes three consecutive nights (`backend/tests/system/test_real_data_rehearsal.py`, Q-02-T48) | builder | Fri Apr 16, 2027 | CI history | open |
| M7-15 | Runbooks rehearsed once on staging and linked from their alarms: RB-27, RB-29, RB-14, RB-25, and agent stage changes (Q-02-T51) | builder | Fri Apr 16, 2027 | [`../../runbooks/README.md`](../../runbooks/README.md) | open |
| M7-16 | Vendor-diligence pack indexed in `docs/ops/diligence/README.md`: SOC 2 report, pen-test letter, DPA and MSA, sub-processor list, WISP, insurance certificate, BAA posture, SQMS 1 Technology Resource Pack (Q-02-T49) | builder | Fri Apr 16, 2027 | `docs/ops/diligence/README.md` | open |
| M7-17 | Dossier `docs/ops/gates/M7-real-data-gate.md` links evidence for every M7 row and is signed by the builder | builder | Fri Apr 16, 2027 | The dossier | open |

## Operating cadence

| Cadence | Control | When |
|---|---|---|
| Quarterly | Access review (`make access-review`) | First one by Fri Dec 11, 2026 |
| Quarterly | Restore drill | First by Fri Dec 11, 2026; Q1 by Fri Mar 26, 2027 |
| Quarterly | Review this tracker and the control map | Same day as the access review |
| Annual | Pen test, risk assessment, provider-terms `review_by`, WISP review | Pen test #2 in Nov 2027; others on their row's date |
| Per change | Update the AI threat model when an agent, tool or data source is added (ADR-064) | In the same change |

## Open items

- **Change management with one person.** Auditors test change management hardest. The plan assumed an approver other than the author; the solo amendment removes that. Compensating controls to evidence: required CI checks on `main`, build-once-and-promote, flag expiry checks, the optional reviewer subagents, and the recorded model behind each change (ADR-083, ADR-084, ADR-088). Settle with the auditor at engagement (M4-11) how the Type I description states this.
- **Dossier and diligence index** (`docs/ops/gates/`, `docs/ops/diligence/`) do not exist yet; Q-02-T49 creates them.
- **Compliance tool** is not yet chosen (decide by Fri Oct 30). Evidence locations in the control map say "tool" until it is.
