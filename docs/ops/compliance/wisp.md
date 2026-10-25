# Accrued written information security plan (WISP) v1

| Field | Value |
|---|---|
| Version | v1 draft, 2026-10-25 (Q-02-T40, TASK-1241) |
| Status | **draft**: not yet approved. The security lead (the Qualified Individual) approves it by **Fri Apr 9, 2027** (M7-09 in [`README.md`](README.md)) |
| Owner | The security lead, designated Qualified Individual in [`README.md`](README.md) §"Qualified Individual designation" |
| Review | ayushkbhatia reviews this draft; counsel's review runs through F-09 and is **open** |
| Frameworks | FTC Safeguards Rule, 16 CFR 314.4 (a) to (j), as a service provider to firms (314.4(f)); Massachusetts 201 CMR 17.00; IRS Pub 4557 and the Pub 5708 WISP format for the firms' appendix |
| Related | [`../soc2-control-map.md`](../soc2-control-map.md) · [`type-1-readiness.md`](type-1-readiness.md) · [`../../architecture/ai-threat-model.md`](../../architecture/ai-threat-model.md) · [`../../specs/SPEC-341-compliance-kernel-real-data-readiness.md`](../../specs/SPEC-341-compliance-kernel-real-data-readiness.md) · [`../../runbooks/README.md`](../../runbooks/README.md) |

**How to read this plan.** Each safeguard names the control Accrued runs, where it lives (code, configuration or document), the evidence an auditor or a firm can ask for, and its state today: **operating** (built and producing evidence), **built** (in code, evidence starts when production does) or **planned** (named task, not yet built). The mapping of each legal element to a control is Accrued's reading for its own programme; **it is not legal advice and counsel has not reviewed it yet**. Every point that needs counsel is listed in §11.

**What stays out of this file.** The repository is public ([`README.md`](README.md) rule 4). People are named by role only ("the security lead", "counsel", "the SOC 2 auditor"). No vendor contract text, prices, account identifiers, addresses or report contents appear here; they are in the document vault and cited by opaque reference.

## 1. Purpose, scope and objectives

**Purpose.** Protect the security, confidentiality and integrity of the customer information that accounting firms entrust to Accrued, against anticipated threats and unauthorised access or use, as the firms' service provider.

**Customer information in scope.** Everything a firm or its clients put into Accrued: client records, engagement and tax return work, evidence files and their extracted text, ledgers and trial balances, messages, and the identifiers of the firm's people and its clients' people. Taxpayer identification numbers, bank account numbers, dates of birth and IP PINs are tagged in code (`pii_kind`), as are tax return information (`tri`) and health information (`phi`) (ADR-167). Accrued's own staff and vendor records are in scope for access control, not as customer information.

**Systems in scope.** The firm app and client portal; the backend API and workers; PostgreSQL with row-level security; S3 evidence and records buckets; Temporal; the AI gateway and its model route; the AWS accounts under the organisation (production, staging, shared, log archive); the GitHub organisation and CI; the identity provider; the email provider; error tracking and observability; the security lead's workstation.

**Objectives.**
1. A firm's data is never visible to another firm.
2. Every person's access is the least their role needs, needs a second factor, and leaves a trail.
3. No AI component decides anything; every decision is a named person's.
4. Data is encrypted in transit and at rest, under a key per firm.
5. Records are kept as long as law and the firm's policy require, held when a matter requires, and disposed of deliberately by two people.
6. Incidents are detected, contained and reported to affected firms within the agreed time.

## 2. Responsibilities

| Role | Responsibility |
|---|---|
| The security lead (Qualified Individual) | Owns this plan; oversees and enforces the programme; approves the risk assessment, exceptions and this WISP; reports annually (§9) |
| The builder | Builds and operates the controls (in the solo edition the builder and the security lead are one person; ADR-100's compensating controls apply) |
| Counsel | Reviews this plan, the DPA notice SLA, retention floors and the provider-terms register (F-09) |
| The SOC 2 auditor | Tests the controls (Type I as of Mon Mar 1, 2027) |
| The penetration tester | Tests the product (Mon Feb 15 to Fri Mar 5, 2027) on synthetic data only |
| Sub-processors | Act under the terms recorded in the sub-processor register (§7) |

**Qualified Individual designation record.** Designated Tue Oct 20, 2026 in [`README.md`](README.md). Scope: the information-security programme, this WISP, the gate tracker, the control map, the AI threat model, incident response and the annual report. Single-person risk and its compensating controls: ADR-100. This record is restated here so the WISP stands alone; the README is the record of designation.

## 3. Safeguards Rule elements, 16 CFR 314.4 (a) to (j)

| Element | Accrued control | Where it lives | Evidence | State |
|---|---|---|---|---|
| **(a)** Qualified Individual | The security lead, designated in writing | [`README.md`](README.md) | Designation record; this WISP's approval | operating |
| **(b)** Written risk assessment | Annual and on major change; includes the AI threat model, the §7216 prerequisites and the exposure of a public repository | [`../../architecture/ai-threat-model.md`](../../architecture/ai-threat-model.md); risk assessment in the compliance tool | Dated assessment (M4-10) | planned (due Fri Dec 11, 2026) |
| **(c)(1)** Access controls | Row-level security on every firm table; one `authorise` per action against the permission matrix; `visible()` on every list; ethical walls; need-to-know for admins; quarterly access review | ADR-014, ADR-023, ADR-024, ADR-026; `docs/architecture/permission-matrix/`; `make access-review` | Generated tenant-isolation and permission-matrix tests (`backend/tests/security/`); access-review exports (M4-07) | built; review planned (Fri Dec 11, 2026) |
| **(c)(2)** Data inventory | Every model field carries a classification; TRI, PHI and PII flags force Restricted; the data map is generated, not typed | ADR-031, ADR-167; `backend/src/abacus/kernel/classification.py` (`sensitive_paths`, `pii_paths`) | Classification check in `make check-fast`; generated data map | built |
| **(c)(3)** Encryption | TLS at the edge and to the database; envelope encryption per firm key; encrypted RDS and S3 | ADR-035, ADR-104; `backend/src/abacus/kernel/crypto/`, `kernel/db_tls.py`; ADR-156 (key provisioning, proposed) | Configuration rules; encryption tests | built in code; per-firm KMS keys planned (Q-01-T27) |
| **(c)(4)** Secure development | Spec-first tasks with acceptance tests; a separate test author for red code; CI stages 1 and 2; the security stage (generated tests, CodeQL, dependency review, pip-audit, Trivy); protected paths | ADR-078, ADR-080, ADR-083, ADR-084; `.github/workflows/ci.yml`, `security.yml`; `docs/architecture/protected-paths.md` | CI history; pen-test report | operating; required-check ruleset planned (F-01) |
| **(c)(5)** Multi-factor authentication | Staff: second factor mandatory (ADR-030); listed sensitive actions need a fresh factor; portal owners and signing or approving scopes need MFA; every Accrued human account (cloud, source control, identity, error tracking, registrar, email) uses MFA | `docs/architecture/fresh-mfa-actions.yaml` and its lint; migration 0133 (portal floor) | Generated fresh-MFA tests; identity-provider reports; `make mfa-report` | partial: lint and portal floor built; staff-route refusal and the MFA report planned (Q-02-T37) |
| **(c)(6)** Secure disposal | Retention per record type with legal floors and a recorded basis; holds override; two-person destruction with certificates; crypto-shredding | ADR-032 to ADR-034, ADR-179 (proposed); migration 0112; `evidence/holds.py` | Destruction certificates (Q-05) | partial: floors, policies and holds built; destruction planned (Q-05) |
| **(c)(7)** Change management | Every change through a pull request on a protected `main`; Terraform by pull request, applied by hand; migrations never edited once on `main` | `AGENTS.md`; `docs/architecture/protected-paths.md`; `infra/` | Source-control audit log; ruleset export | operating |
| **(c)(8)** Monitoring of user activity | Append-only, attributed audit log, hash-chained and anchored; identifier-only access events for content reads; cloud audit logging to the log archive | ADR-007, ADR-159 (proposed); migrations 0096, 0105, 0106 | Audit-log exports; chain verification (`make audit-chain-verify`) | built; checkpoint and anchor schedules planned |
| **(d)** Testing and monitoring | Continuous vulnerability scanning of images and dependencies; scans at least every six months; annual penetration test | `.github/workflows/security.yml`; [`../pentests/`](../pentests/) | Scan reports; pen-test report and retest letter | partial: CI scans operating; pen test #1 booked |
| **(e)** Training | Annual security and phishing training; secure-coding module | Compliance tool | Training records (M4-09) | planned (Fri Dec 11, 2026) |
| **(f)** Service-provider oversight | Sub-processor register with each provider's terms, data handled and region, reviewed yearly; client data reaches a model only through a provider entry with counsel's second approval | [`../../operations/sub-processors.yaml`](../../operations/sub-processors.yaml); [`../../operations/provider-terms.yaml`](../../operations/provider-terms.yaml); ADR-113 to ADR-115 | Register reviews; provider-terms approvals | partial: registers built; the model-provider entry awaits counsel (Q-02-T18) |
| **(g)** Adjust the programme | Quarterly security review; every incident's actions become a test, a lint or an ADR | ADR-097; this plan's review cadence (§9) | Review minutes | planned |
| **(h)** Incident response plan | Severity classes, containment, notification and post-incident review; the incident register with the FTC clock for each firm | ADR-097; [`../../runbooks/README.md`](../../runbooks/README.md) (RB-08, RB-27); migration 0143 | Tabletop record (M4-08); runbooks | partial: register built; runbooks being written |
| **(i)** Report to the board | The security lead's written report each December on the programme's status, risk, incidents and recommendations | Compliance tool | Dated report | planned (Dec 2026) |
| **(j)** Notification to the FTC | The firm's obligation for its own customers (unencrypted information of 500 or more consumers, within 30 days of discovery). Accrued notifies the affected firm within the DPA's time from its own confirmation and creates the firm's register entry with Accrued's facts, so the firm's clock starts with facts | `platform/incidents.py` (clock, propagation); RB-27 | DPA notice clause (vault); propagation records | built in code; notice time awaits counsel |

## 4. Massachusetts 201 CMR 17.00

One plan serves both rules. The crosswalk below maps the regulation's WISP elements and computer-system requirements to the controls in §3. Accrued's reading; counsel review open.

| 201 CMR 17.00 requirement | Where in this plan |
|---|---|
| 17.03(2)(a) Designate one or more employees to maintain the programme | §2 (the security lead) |
| 17.03(2)(b) Identify and assess reasonably foreseeable risks; evaluate safeguards (training, compliance, detection and prevention) | §3 (b), (e), (d); §6 |
| 17.03(2)(c) Policies for storing, accessing and transporting records outside business premises | §5 (workstations and remote access) |
| 17.03(2)(d) Disciplinary measures for violations | §8 |
| 17.03(2)(e) Prevent terminated employees from accessing records | §5 (offboarding) |
| 17.03(2)(f) Oversee service providers, by contract | §3 (f); §7 |
| 17.03(2)(g) Reasonable restrictions on physical access | §5 (no Accrued premises hold records; cloud provider's physical controls through its attestation) |
| 17.03(2)(h) Regular monitoring that the programme operates | §3 (c)(8), (d); §9 |
| 17.03(2)(i) Review the scope of security measures at least annually or on a material change | §9 |
| 17.03(2)(j) Document actions taken in response to an incident | §3 (h); the incident register and post-incident review |
| 17.04(1) Secure user authentication protocols | §3 (c)(5); ADR-030 |
| 17.04(2) Secure access control measures | §3 (c)(1) |
| 17.04(3) Encryption of records and files transmitted across public networks or wirelessly | §3 (c)(3) (TLS) |
| 17.04(4) Reasonable monitoring for unauthorised use of or access to personal information | §3 (c)(8) |
| 17.04(5) Encryption of personal information on laptops and portable devices | §5 (full-disk encryption; no client data on workstations) |
| 17.04(6) Firewall protection and security patches for systems connected to the internet | §5; infrastructure security groups and managed patching (Q-01) |
| 17.04(7) Current system security agent software with malware protection | Upload malware scanning, fail closed (ADR-153, proposed; `kernel/scanning.py`); workstation agent (§5) |
| 17.04(8) Education and training of employees | §3 (e) |

## 5. Workstations, remote access and people

- **No client data on workstations.** Development and tests run on the synthetic Brightwater Hale tenant only; local builds, migrations and seeds never point at a hosted database (`AGENTS.md` rules 16 and 17; the scenario loader refuses non-loopback databases).
- **Workstation baseline.** Full-disk encryption, screen lock, OS updates and the compliance tool's device agent (M4-06).
- **Remote access.** All access is remote, over TLS, through the identity provider with MFA; cloud access is through single sign-on with short-lived roles; there are no shared accounts.
- **Joiners and leavers.** Access is granted by role through the identity provider and removed the day a person leaves; the quarterly access review catches anything missed.
- **Physical access.** Accrued keeps no records on premises; the cloud provider's physical controls are covered by its attestation, reviewed under §7.

## 6. Risk assessment

The risk assessment is a dated document in the compliance tool, refreshed yearly and on any material change (a new data class, a new sub-processor, a new model route, a new write to a client system). It draws on:
- the AI threat model ([`../../architecture/ai-threat-model.md`](../../architecture/ai-threat-model.md)): prompt injection through client documents, cross-tenant exposure, model access to tax return information, agent overreach;
- the plan's risk register (`docs/plan/11-risk-register.md`);
- pen-test findings and their retest status;
- incidents and near misses.

Each risk names its control and its evidence, and a risk with no control is either accepted in writing by the security lead with a review date or becomes a task.

## 7. Service providers

- Every sub-processor that may touch customer information is in [`../../operations/sub-processors.yaml`](../../operations/sub-processors.yaml) with the data it handles and its region; the list in the DPA and the diligence pack is generated from it (P-67), never typed.
- Before customer information reaches a provider, its contract terms (confidentiality, use limits, security, breach notice, sub-processing) are reviewed and recorded in the vault; model providers additionally need a current provider-terms entry with counsel as second approver (ADR-114).
- Each provider's assurance report is collected and reviewed yearly.

## 8. Enforcement

A person who breaks this plan loses access while the matter is reviewed; the security lead records the outcome. A control failure found by any means is handled as an incident under §3 (h) and ends in a test, a lint rule or an ADR, so it cannot recur silently (ADR-097; `AGENTS.md` "When you make a mistake twice").

## 9. Review cadence and reporting

| Activity | When |
|---|---|
| Access review | Quarterly (`make access-review QUARTER=<YYYYQn>`) |
| Security review of the programme | Quarterly |
| Risk assessment | Yearly and on material change |
| Penetration test | Yearly, plus a delta test before each new real-data surface |
| This WISP | Yearly and on material change; version and approval recorded below |
| Report to the security lead's board equivalent (§3 (i)) | Each December |

## 10. Approval record

| Version | Date | Approved by (role) | Notes |
|---|---|---|---|
| v1 | — | the security lead (pending; due Fri Apr 9, 2027) | ayushkbhatia review pending; counsel review open through F-09 |

## 11. Open items

**For counsel (through F-09; nothing here is settled until counsel answers):**
1. Whether this element-by-element mapping is a sufficient WISP for Accrued as a service provider under 314.4(f), and under 201 CMR 17.00 for Massachusetts residents' information.
2. The incident notice time to firms written into the DPA (the code uses 72 hours from Accrued's confirmation; SPEC-341 §20).
3. Whether IRS Pub 1075 applies to any of Accrued's processing (the plan reads it as not applying; to confirm).
4. The retention basis per record type that justifies keeping customer information beyond the disposal rule's default (314.4(c)(6); ADR-179).
5. HIPAA: whether any engagement may carry PHI before a business-associate chain exists (the `phi` flag exists; the posture is F-09's).

**For the builder (gaps between this plan and the code; each is a named task):**
1. Staff routes do not yet refuse a session without a verified second factor, and `make mfa-report` does not exist (Q-02-T37).
2. The audit-chain checkpoint, nightly verification and daily anchor jobs, the retention clock and access-event partition jobs wait for Temporal Schedules (Q-01-T26).
3. The firm export is a contract stub (Q-02-T43).
4. Destruction batches and certificates are not built (Q-05).
5. The runbooks RB-08 and RB-27 are not written yet (runbook programme).
6. The risk assessment, training, tabletop and first access review are due Fri Dec 11, 2026 (M4).

## Appendix A. Accrued controls, in Pub 5708 format, for a firm's own WISP

A firm that uses Accrued writes its own WISP (IRS Pub 5708 gives a template; Pub 4557 lists safeguards). Accrued is one of the firm's service providers. This appendix is the text a firm can attach under its service-provider section; ADM-06 (Security center, G-02) prefills it for each firm. The example firm is the synthetic Brightwater Hale LLP.

**A.1 Provider and purpose.** Accrued is the practice platform the firm uses for audit, tax and client-accounting work: client records, requests and evidence, workpapers and the client portal. It processes the firm's client information only to provide that service.

**A.2 Responsible individuals.** Accrued's security programme is overseen by its designated Qualified Individual. Within the firm, the firm's own Qualified Individual (at Brightwater Hale, the IT and security lead) administers Accrued's security settings, the firm's incident register and its export.

**A.3 Safeguards Accrued operates for the firm.**
- *Separation:* the firm's data is isolated from every other firm's by database row-level security on every table, tested on each change.
- *Access:* the firm's people sign in through the firm's identity settings with a second factor; access follows roles and engagement membership; ethical walls and need-to-know limits apply; sensitive actions (lifting a wall, exports, legal holds, AI opt-in, revealing a TIN) need a fresh second factor.
- *Encryption:* in transit by TLS; at rest with envelope encryption under a key for the firm.
- *Activity trail:* every change is recorded with the person who made it, and every read of client content leaves an access record; the trail is append-only and hash-chained.
- *AI:* the Accrued Agent prepares work and cites its sources; a named person makes every decision. Client data reaches a model only after the firm opts in, through a provider recorded with its terms, and never with an unmasked TIN in the model's context.
- *Retention and holds:* the firm sets retention per record type at or above the legal minimum; legal holds stop any deletion; destruction needs two of the firm's people.
- *Export:* the firm can export all of its data, approved by two of its people.

**A.4 Incidents.** If Accrued has an incident affecting the firm's information, Accrued notifies the firm's Qualified Individual within the time agreed in the DPA and creates an entry in the firm's incident register with Accrued's facts, so the firm's own FTC clock (30 days for 500 or more consumers' unencrypted information) starts with facts. Example (synthetic): Brightwater Hale's register shows INC-2026-005, discovered Thu Sep 10, 2026, at day 4 of 30 on Mon Sep 14.

**A.5 Evidence the firm can request.** Accrued's SOC 2 report (under NDA), its penetration-test attestation letter, the sub-processor list, this WISP's control summary, and the firm's own audit-log and access-event exports.

**A.6 Review.** Accrued reviews these controls at least yearly; the firm reviews this appendix with its own WISP.
