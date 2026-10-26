---
id: SPEC-341
title: "Compliance kernel and real-data readiness (Q-02): classification flags, attribution, the human-only guard, access events, the audit hash chain, retention, Object Lock classes, legal holds, the incident register, firm export, the fresh-MFA list and run records"
status: draft
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-016, ADR-031, ADR-032, ADR-033, ADR-034, ADR-036, ADR-097, ADR-113, ADR-114, ADR-115, ADR-159, ADR-161, ADR-167, ADR-169]
related_specs: [SPEC-036, SPEC-050, SPEC-051, SPEC-304]
created: 2026-10-25
updated: 2026-10-25
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves. The AC numbers are the epic's (`docs/plan/epics/Q-02.md` §3, AC-1 to AC-46), so the tests already on `main` that cite "Q-02 AC-n" cite this spec.
> - Solo edition (`docs/plan/AMENDMENT-solo.md`): "N", "AY" and "both founders" in the epic read as "the builder". Counsel's answers are never defaulted (DEC-71).
> - This spec was written after most of the kernel was built (Q-02-T04, TASK-1239). Each AC carries its state on `origin/main` at `9d7826d7`: **built**, **partial** or **not built**, with the files that hold it. Where the code chose a different name than the epic, the code's name is used here and the decision that chose it is cited.

## 1. Summary
The compliance kernel is what must be true in code before any firm puts real client data into Accrued (the M7 gate, Fri Apr 16, 2027; chapter 01 §1.2.2): every field carries a classification and, where it applies, a TRI, PHI or PII flag; every audit row names its person; no agent or policy actor can record a human decision; reads of client content leave an identifier-only trail; the audit log is hash-chained and anchored; retention has legal floors and longer firm policies; stored objects carry Object Lock by record class; legal holds override everything; incidents run on the FTC clock; a firm export needs two people; listed actions need a fresh second factor; and decision-relevant agent runs leave a durable record. This spec numbers those rules, marks what is built, and points at the contract (`docs/contracts/compliance-kernel.md`) consumers build against.

## 2. Problem and context
- Epic Q-02 (`docs/plan/epics/Q-02.md`) wrote 46 ACs in §3 and asked T04 for the SPEC. Most kernel rows were built before this spec existed (S3 to S8, TASK-416, 417, 919, 920, 940, 965, 968, 1013, 1014, 1160, 1170, 1200, 1201), each citing the epic's AC numbers. This spec gives those tests one home and records what is left.
- SPEC-036 (data boundary for real firms) owns TASK-076's behaviour. AC-1 to AC-9 below restate its kernel-facing parts so the M7 dossier can cite one list; SPEC-036 stays the source for its own wording.
- SPEC-051 (sprint-0 setup) and SPEC-050 (landing zone) are referenced, not repeated.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Firm admin (Grace Holloway in the seed) | Opts the firm in to AI on client data; manages retention policies; places holds |
| Security admin, the firm's Qualified Individual (Felix Andersen) | Records incidents; requests firm exports; manages retention; places holds |
| Partner-level member (Victor Hammond, Neil Ashcroft, Margaret Okonkwo) | Places and lifts holds; approves a firm export; excludes an engagement from AI |
| Staff (Ana Cruz) | Reads evidence (leaves access events); acts through the Agent ("Ana Cruz via Agent") |
| The Accrued Agent | Proposes only; every write it causes names the person it acted for; denied every human-only action |
| The system | Scheduled work: checkpoints, anchors, retention extension, hold application, incident propagation |
| Platform staff (the builder) | Imports and publishes floor sets (two people); sets agent stages; propagates Accrued incidents |
| Counsel | Supplies the legal floors and confirms the notice SLA (F-09); never defaulted |

## 4. Goals and non-goals
**Goals**
- One numbered list of the kernel's rules with their state and evidence.
- A contract (`docs/contracts/compliance-kernel.md`) that names every consumer epic, its sprint and how each slot fails closed.

**Non-goals**
- The screens (ADM-04, ADM-06, ADM-07 are G-02's; FIL-02 is Q-05's).
- Destruction batches, crypto-shred and certificates (Q-05), the §7216 consent gate (T-01, C19), archive seal and lock triggers (A-07), the monthly export schedule (G-02).
- Legal floor values. They are content set with counsel and published through the two-person import (Q-02-T31); none appears in this spec or any commit.

## 5. User stories and acceptance criteria

### Story 1: AI on a firm's real data (SPEC-036; TASK-076)
- **AC-1** Given a non-synthetic firm without an opt-in, when any specialist calls the gateway on the client-data route, then the call is refused with reason `firm` before any network call, `ai.boundary_refused` is audited, and the work is never retried or rerouted. **Built** (`ai_gateway/boundary.py`; `tests/integration/agent_tests/test_gateway_boundary.py`, `tests/unit/agents/test_boundary_refusal_is_terminal.py`).
- **AC-2** Given a firm admin whose second factor is older than the `mfa_recent` window, when they opt in, then 401 `mfa_required`; with a fresh factor the firm records `ai_client_data_at`, `_by` and `_version`, audited by name. Any other role is refused. **Built** (migration `0056_client_data_optin_stages.py`; `identity/routes.py`, `identity/firm_settings.py`; matrix `firm.ai_client_data` in `docs/architecture/permission-matrix/identity.yaml`).
- **AC-3** Given the disclosure read, then provider, region, training, retention and sub-processors come from the compiled register (`kernel/_provider_terms.py`) with each specialist's stage, and never name Anthropic as the processor. **Partial**: the generated disclosure is built (TASK-076); the register has no Bedrock entry until Q-02-T18, so real firms read "no current entry" and stay refused.
- **AC-4** Given an opted-in firm and an agent without a stage row, then its stage is `off`; the first stage that can be set is `shadow`; `live` is refused unless the agent was in `shadow` for that firm. **Built** (`agents/stages.py`, `abacus_tools/agent_stage.py`; `tests/unit/agents/test_agent_stages.py`).
- **AC-5** Given an agent in `shadow` for a firm, then its runs are recorded and every firm-facing read of its output returns nothing from them. **Partial** (Q-02-T08): the screener's reads filter shadow runs; the upload-review, inbox-match, guidance-draft and human-gate reads are not yet proven by the T09 suite.
- **AC-6** Given a partner excludes an engagement with a reason, then every agent call on it is refused (`engagement`), and the exclusion and its lifting are audited with the partner as actor. **Built** for the route and refusal (`engagement.ai_exclude`); the screen half and SPEC-036 AC-9 states are P-07's and G-02's (Q-04-T351).
- **AC-7** Given the register's entry changes training, retention, region or sub-processors, then every opted-in firm reads `opt_in_required` and is refused until it opts in again; a `review_by` change alone does not reset it. **Partial** (Q-02-T08): the version is recorded at opt-in; the re-opt-in comparison waits for the first real entry (Q-02-T18).
- **AC-8** Given an opt-out, then the next call is refused, workers refuse at the next run start after `firm.ai_client_data_changed`, and in-flight calls elsewhere stop within the 60-second cache period. **Partial** (Q-02-T08).
- **AC-9** Given a real firm with every setting on, then no model-written text reaches a client principal (ADR-111). **Built** by construction (no client route serves agent text); the T09 independent suite is **not built**.

### Story 2: Bedrock clearance for the three specialists
- **AC-10** Given staging after R0, when `make route-parity ROUTE=bedrock` runs, then the report is committed with its SHA-256; at M7 and on Jun 1 the report in force is under 90 days old. **Not built** (Q-02-T11).
- **AC-11** Given each specialist, then `client_data: cleared` appears in its spec only in the same PR as a committed, signed, passing Bedrock full-suite report at the current prompt version. **Partial**: the spec check exists (TASK-075); no specialist is cleared (Q-02-T44).
- **AC-12** Given the evaluation thresholds, then no PR lowers one; a failing agent stays synthetic-only. **Built** as a rule (AGENTS.md rule 13; `evals/*/suite.yaml` protected).
- **AC-13** Given P-03's masked agent material, then final clearance runs on it. **Not built** (Q-02-T44 after P-03-T15).
- **AC-14** Given a firm and agent in shadow, when staff promote to live, then the note links a shadow report meeting the SPEC-036 Q1 floor and QD-10, recomputed by the stage action. **Partial**: the Q1 floor (50 runs, 14 days) is enforced by `abacus_tools/agent_stage.py`; QD-10 and the versioned report are Q-02-T50.

### Story 3: Actor attribution and the human-only guard (INV-1, INV-5)
- **AC-15** Given an agent run started by a person, when it records an audit event, then the row has `actor_kind = 'agent'` and `on_behalf_of_user_id` = that person, bound to the transaction setting `app.on_behalf_of`; a new agent row without a person is refused. **Built** (migrations `0096_audit_attribution.py`, `0108_audit_behalf_is_transaction.py`; `kernel/uow/__init__.py`; `tests/integration/test_audit_attribution.py`, `test_q02_attribution_access_acceptance.py`).
- **AC-16** Given the dormant `policy` actor, then a `policy` row needs `policy_ref`, and no code outside `kernel` builds a policy context. **Built** (0096 CHECK; banned pattern `_check_policy_context` in `abacus_tools/quality/banned_patterns.py`).
- **AC-17** Given `docs/architecture/human-only-actions.yaml`, when any transaction inserts a listed action with `actor_kind` `agent` or `policy`, then the database raises before commit, independent of the matrix. **Built** (migrations `0097`, `0098`, `0125` and every later migration that redefines `abacus_human_only_actions()`; generator `abacus_tools/codegen/human_only_actions.py` → `kernel/_human_only_actions.py`; `tests/integration/test_human_only_guard.py`).
- **AC-18** Given every write the unit of work records with an engagement or work item in scope, then `engagement_id` and `work_item_id` are set. **Built** (`tx.record(..., scope=...)`, 0096 partial indexes).

### Story 4: Classification flags and PII in model context
- **AC-19** Given a field declared `classified("restricted", pii_kind="tin")`, then its JSON schema carries the flag, `pii_paths(model, "tin")` finds it, and `tri`, `phi` or `pii_kind` on anything but `restricted` fails at import. **Built** (`kernel/classification.py`; DEC-295; `tests/unit/kernel/test_classification_flags.py`).
- **AC-20** Given `mask(value, "tin")`, then only the last four digits show; bank numbers keep the last four; `ip_pin` and `date_of_birth` mask fully. **Built** (`kernel/classification.py` `mask`).
- **AC-21** Given a log line, Sentry event or metric attribute built from a tagged value, then the value is scrubbed. **Built** (`tests/unit/kernel/test_pii_scrubbing.py`).
- **AC-22** Given a gateway call whose context holds a valid unmasked SSN, ITIN or EIN pattern, then the gateway refuses it with `pii_in_context` before any network call, audits it and never retries. **Built** (`kernel/tin_patterns.py`; `ai_gateway/__init__.py` `refuse_pii_in_context`; `tests/integration/agent_tests/test_gateway_pii_refusal.py`, `tests/unit/ai_gateway/test_pii_in_context.py`). The T52 independent suite is **not built**.

### Story 5: Access events
- **AC-23** Given a person downloads an evidence version or opens its rendition, then one `access_events` row records tenant, actor, kind `evidence_content.read`, the subject, client and engagement, and no file name, quote or value. **Built** (migration `0105_access_events.py`; `kernel/uow/access.py`; `evidence/access.py`; `tests/integration/test_access_events.py`).
- **AC-24** Given the gateway builds a model context from evidence versions, then one row per version names the run. **Built** under the as-built kind `model_context.built` (`ai_gateway/__init__.py`).
- **AC-25** Given another tenant's session, then it cannot read the rows, and no role can update or delete one. **Built** (forced RLS and insert-only trigger per partition; generated `tests/security/test_tenant_isolation.py`). Partition creation runs by hand (`ensure_partitions`) until its Temporal Schedule exists; partitions reach March 2027 and a DEFAULT partition catches a late month (TASK-919).

### Story 6: The audit hash chain (ADR-007; ADR-159, proposed)
- **AC-26** Given new audit events for a tenant, then within 5 minutes plus the 120-second settle window a checkpoint seals them: leaf = SHA-256 of the canonical row (leaf version 1, including `occurred_at` and `effective_at`), Merkle root over the range, chain hash over the previous hash, root, range and count. **Partial**: sealing, leaf v1, root and chain hash are built (migration `0106_audit_checkpoints.py`; `kernel/uow/chain.py`; `tests/integration/test_audit_chain.py`); the 5-minute `AuditCheckpointJob` schedule is **not built**, so sealing runs through `make audit-chain-verify` and `python -m abacus_tools.audit_chain seal`.
- **AC-27** Given an audit row altered or deleted outside the app, when the verifier runs, then it reports the first broken checkpoint and raises the SEV1 alarm. **Partial**: `verify_chain` and the metric `abacus.audit_chain.mismatch` are built (`tests/integration/test_q02t27_chain_independent.py`); the nightly `AuditChainVerify` schedule and the alarm's runbook link are not.
- **AC-28** Given a row with a `seq` inside an already-closed range, then the verifier flags a late commit. **Built** (`test_q02t27_chain_independent.py`).
- **AC-29** Given a day's checkpoints, then a daily anchor object with the last chain hash is written to the `records` bucket in COMPLIANCE mode with retain-until of at least 7 years. **Partial**: `evidence.api.anchor_chain` and `verify_anchor` are built (`evidence/records.py`, `kernel/uow/chain.py`); the daily `AuditAnchorDaily` schedule and the restore-drill step (Q-03-T053) are not.

### Story 7: Retention floors, policies and Object Lock (DEC-71, DEC-156, DEC-168)
- **AC-30** Given a floor set imported by one platform admin, then it is not published until a different admin approves; no floor value appears in any commit. **Built** (migration `0112_retention.py` definers `retention_set_import`, `retention_set_publish`; `evidence/retention.py`, `evidence/retention_routes.py`; `tests/integration/test_retention_policies.py`). The content (Q-02-T31) waits on counsel.
- **AC-31** Given a firm policy below its published floor, then 422 `below_floor` and nothing changes; a locked policy is never shortened (`policy_locked`). **Built** (trigger `retention_policy_guard`; routes `GET`/`PUT /v1/retention/policies`, actions `retention_policy.read`/`retention_policy.update` per DEC-227). Until a firm has a policy for a record type, the published floor applies, never a literal; the published default set is applied at provisioning (`platform/provisioning.py` `apply_retention_defaults`) and by the back-fill command.
- **AC-32** Given an upload, then its Object Lock retain-until comes from its record class's policy and is never earlier than the policy expiry; when an anchor event is registered, the retain-until is extended and `retention.extended` is audited as the system. **Partial**: `retain_until_for`, `extend_retention_for` and `storage.put(..., retain_until=)` are built (`tests/integration/test_retention_object_lock.py`); the daily `RetentionClock` schedule is not.
- **AC-33** Given seal manifests, consent and signature evidence and chain anchors, then they are written to the `records` bucket in COMPLIANCE mode; evidence stays GOVERNANCE; on staging the app role's governance bypass is denied. **Partial** (TASK-968 in progress): the COMPLIANCE writes are built (`evidence/records.py`); the Terraform deny and the staging check are the human's to apply.

### Story 8: Legal holds (DEC-228, DEC-229)
- **AC-34** Given a partner-level member with fresh MFA places a hold on a client and tax year with a reason, then every version in scope is counted in `hold_objects`, `LegalHoldApply` sets the S3 object legal hold per version, the notify list gets `legal_hold_placed`, and the audit row names the person. A Staff user is refused. **Built** (migration `0126_legal_holds.py`; `evidence/holds.py`, `evidence/hold_routes.py`, `evidence/workflows.py`; `tests/integration/test_legal_holds.py`, `tests/workflows/test_legal_holds_replay.py`).
- **AC-35** Given two overlapping holds, when one is lifted, then the object stays held until no open hold covers it. **Built**.
- **AC-36** Given a new upload into a held scope, then it is held in its creating transaction, before processing. **Built** (`inherit_holds`).
- **AC-37** Given a purge or destruction asks the hold check, then held versions are excluded; with no hold check registered, the caller fails closed and erases nothing. **Built** (`kernel/holds.py` `erasable_versions`, `HoldCheckMissing`; P-06's withdrawal purge in `evidence/withdrawals.py`; `tests/unit/kernel/test_holds.py`, `tests/integration/backfill/test_q02t36_retention_and_holds.py`). The nightly S3 reconciliation is **not built** (DEC-229).

### Story 9: The incident register and the FTC clock (DEC-290)
- **AC-38** Given the QI records an incident discovered Thu Sep 10, 2026 with 600 unencrypted consumers, then `notification_event` is true and `ftc_notify_by` is Sat Oct 10, 2026 (calendar days in the firm's time zone, no business-day roll); with 499, or encrypted data, it is false; on Mon Sep 14 the clock reads day 4 of 30. **Built** (migration `0143_security_incidents.py`; `platform/incidents.py`, `platform/incident_routes.py`; `tests/integration/test_security_incidents.py`, `tests/unit/platform/test_incident_clock.py`).
- **AC-39** Given an Accrued-side incident affecting several firms, when staff propagate it, then each firm gets an entry with `source = 'accrued'`, Accrued's facts, `dpa_notice_at` within 72 hours of confirmation, the system as actor, and an `incident_from_accrued` notification to the QI. **Built** (`IncidentPropagationWorkflow`; `make incident-propagate`; `tests/workflows/test_incident_propagation_replay.py`). The 72-hour figure awaits counsel's DPA confirmation (§20).

### Story 10: Firm export with dual approval (DEC-72)
- **AC-40** Given the security admin requests an export naming a partner as approver, when the requester tries to approve it, then 409 `approver_must_differ`; when the named approver approves with fresh MFA, then the export is built, encrypted under the tenant key with a SHA-256 manifest, and both are notified. **Partial**: the contract stub is built (`evidence/firm_export_contract.py`, flag `compliance.firm_export`, 404 off and 501 on; `tests/contracts/compliance_kernel/`); the table, workflow and live routes are Q-02-T43.
- **AC-41** Given a ready export, then a download link lives 15 minutes and can be minted for 7 days from approval, each download needs fresh MFA and leaves an access event; after day 7 the archive is deleted and the status reads Expired. **Not built** (Q-02-T43).

### Story 11: MFA enforcement (DEC-330)
- **AC-42** Given `docs/architecture/fresh-mfa-actions.yaml`, when a listed action lacks `mfa_recent: required` in the matrix, then CI fails. **Built** (`abacus_tools/quality/fresh_mfa.py` in `make check-fast`; generated `tests/security/test_fresh_mfa_generated.py`).
- **AC-43** Given a staff session without a verified second factor, then every staff route answers 401; given a portal owner or a holder of a signing or approving scope, then P-08's slot requires MFA before those routes, on staging and production by Fri Apr 16; `make mfa-report` lists coverage. **Partial**: the portal floor is built (migration `0133_portal_mfa.py`, P-08-T17); the staff-route refusal waits for WorkOS MFA in each environment; the deliverable-scope floor waits for a deliverable grant kind; `make mfa-report` is **not built** (TASK-1200).

### Story 12: Run records and the C6 v1 stub (ADR-169, accepted)
- **AC-44** Given a specialist run completes, then one insert-only `agent_run_records` row holds the capability, spec and prompt versions with the prompt SHA-256, model, route, region, register version, boundary basis, input hashes, records read, citations, outcome, initiator and `record_sha256`, still readable after raw traces expire. **Built** (Q-02-T41, TASK-1287; DEC-396): migration 0171, `agents/run_records.py`, the `run_record_v1` patch in the five specialist workflows, `GET /v1/agent-runs/{run_id}/record`.
- **AC-45** Given the C6 v1 run reads, then they return the run summary with the legacy state map and `run_record_sha256`, visible only to people who can read the engagement; walled runs answer 404. **Partial**: the C6 v0 routes exist (`agents/runs_routes.py`, `docs/contracts/agent-runs.md`); the v1 stub and `run_record_sha256` are Q-02-T45.

### Story 13: The security stage
- **AC-46** Given R1, then the `security` stage (generated tenant isolation, permission matrix and route introspection; CodeQL; dependency review; pip-audit; Trivy) is a required check on `main`. **Partial**: the generated suites and `.github/workflows/security.yml` are built (TASK-376, TASK-411); making it a required ruleset check is the human's (F-01).

**Invariants across the spec.** INV-1: every new write action is denied to the agent in the matrix and listed in `human-only-actions.yaml` where it records a human decision. INV-3: every table here is tenant-scoped with forced RLS except the platform reference sets (`retention_floors`, `retention_policy_defaults`), which are read through definers. INV-5: every audit event names a person, "‹person› via Agent", or the system.

## 6. Behaviour and flows
**Happy path (a held, retained, chained record)**
1. A client uploads into an engagement; the version is stored with retain-until from its record class (AC-32) and counted under any open hold covering its scope (AC-36).
2. A person reads it; an access event is written before the content is served (AC-23).
3. Every state change writes an attributed audit row (AC-15, AC-18); checkpoints seal them and anchors land in COMPLIANCE storage (AC-26, AC-29).
4. A purge or destruction asks the hold check and erases only unheld versions (AC-37).

**State transitions**
| Entity | From | Event | To | Who |
|---|---|---|---|---|
| Legal hold | — | placed | applying | firm admin, security admin, partner level (fresh MFA) |
| Legal hold | applying | every version held in S3 | active | system |
| Legal hold | active | lifted | releasing | firm admin, security admin, partner level (fresh MFA) |
| Legal hold | releasing | S3 holds cleared where no other hold covers | released | system |
| Floor or default set | draft | published by a second admin | published | platform staff |
| Firm export | awaiting_approval | approved / declined | building / declined | the named approver (fresh MFA) |
| Agent stage | off | set | shadow | platform staff |
| Agent stage | shadow | Q1 floor (and QD-10, T50) met | live | platform staff |

## 7. Domain and data changes
- **Tables (built):** `firms.ai_client_data_*`, `agent_stages` (0056); `audit_events` attribution columns (0096, 0108); `access_events`, monthly partitions (0105); `audit_checkpoints`, `audit_anchors` (0106); `retention_floors`, `retention_policy_defaults`, `retention_policies`, `retention_policy_versions` (0112); `legal_holds`, `hold_objects` (0126); `security_incidents` (0143).
- **Tables (not built):** `firm_exports` (Q-02-T43). `agent_run_records` is built (0171, Q-02-T41).
- **Invariants:** a firm policy is never below its published floor; a hold is never bypassed; an agent or policy actor never records a human-only action; access rows and checkpoints are insert-only.
- **Retention:** the floors are counsel's content (§20); this spec holds no number.

## 8. Interfaces
The consumer-facing surface, with each slot's fail-closed behaviour, is `docs/contracts/compliance-kernel.md` (v1.2). Routes: `GET`/`PUT`/`DELETE /v1/firm/ai-client-data`; `PUT`/`DELETE /v1/engagements/{id}/ai-exclusion`; `GET /v1/retention/policies`, `PUT /v1/retention/policies/{record_type}/{service_line}`; staff floor and default-set import and publish routes; `GET`/`POST /v1/legal-holds`, `POST /v1/legal-holds/{id}/release`; `POST /v1/firm/security/incidents`; staff `POST /v1/platform/incidents/{accrued_ref}/propagate`; the firm-export stub family. Internal: `classified`, `mask`, `pii_paths`; `kernel.access.record_reads`, `register_access_kind`; `tx.record(scope=...)`; `audit_trail.api.latest_checkpoint`, `verify_chain`; `evidence.api.holds_covering`, `kernel.holds.erasable_versions`; `evidence.api.retain_until_for`, `extend_retention_for`, `anchor_chain`; `platform.api.incident_clock`.

## 9. Authorisation and tenancy
- **Tenant scoping:** every firm table uses `tenant_table()` with forced RLS; reference sets are global and read through `SECURITY DEFINER` functions registered in `schema_check.py`.
- **Who can do what:** the permission-matrix rows in `docs/architecture/permission-matrix/{identity,engagements,evidence,platform}.yaml`; every write action denies `agent` and `system` where a person must act; listed actions need `mfa_recent`.
- **Ethical walls:** walled runs and holds answer 404 (INV-3).
- **Client-side access:** portal principals reach none of these routes (INV-4).

## 10. AI behaviour
N/A for the kernel itself: it makes no model calls. It constrains them: the boundary (AC-1 to AC-9) and the PII refusal (AC-22) run before any network call.

## 11. Integrations
- **S3 Object Lock** (`evidence` GOVERNANCE, `records` COMPLIANCE). Holds are idempotent per version; a failed S3 call leaves the hold `applying` and the database still refuses deletion.
- **Temporal:** `LegalHoldApply`, `LegalHoldRelease`, `IncidentPropagation` run today; the checkpoint, verify, anchor, retention-clock and partition schedules wait for Temporal Schedule plumbing (Q-01-T26).
- **AWS KMS:** the export archive key (Q-02-T43).

## 12. Edge cases and failure modes
- No hold check registered: every purge raises `HoldCheckMissing` and erases nothing.
- No published floor or policy for a record class: retain-until falls back to `evidence_retention_days` (floor 365), never to a literal year count.
- An audit row committed late into a closed range: reported as a late commit, distinct from tampering (SEV2 until investigated).
- A discovery time in the future: refused (`discovered_in_future`).
- A repeat propagation with changed facts: refused and nothing written.

## 13. Security and privacy
- **Data classification:** every model field is classified; TRI, PHI and PII flags force Restricted (ADR-167).
- **Threats considered:** cross-tenant reads, agent self-approval, audit tampering, deletion of held records, TINs in model context, export by one person. Mapped in `docs/architecture/ai-threat-model.md`.
- **Mitigations:** RLS, the human-only guard, the hash chain and COMPLIANCE anchors, the hold check, the PII refusal, dual approval with fresh MFA.

## 14. Audit trail and evidence integrity
Audit actions: `firm.ai_client_data_opted_in`/`_opted_out`, `engagement.ai_excluded`/`ai_exclusion_lifted`, `agent_stage.changed`, `ai.boundary_refused`, `retention_floor.imported`/`published` (as-built set events), `retention_policy.updated`, `retention_policy.defaults_applied`, `retention.extended`, `legal_hold.placed`, `legal_hold.counted`, `legal_hold.activated`, `legal_hold.lifted`, `incident.recorded`, `incident.propagated`, `firm_export.*` (Q-02-T43). Access events are kept apart from audit events on purpose (volume).

## 15. Observability
Metric `abacus.audit_chain.mismatch` (SEV1). Logs never carry tagged values (AC-21).

## 16. Performance and scale
Checkpoints seal at most 50,000 events per run; a backlog seals over several runs. Holds apply in batches of 200 stored versions per activity.

## 17. UX
None in this epic. Facts arrive as words and numbers so consumer screens never encode meaning in colour: the clock as `clock_day` of `clock_days`, stages as words, masked values already masked.

## 18. Test plan
| AC | Test type | Where |
|---|---|---|
| AC-1 to AC-9 | integration, unit; independent suite T09 (not built) | `agent_tests/test_gateway_boundary.py`, `unit/agents/` |
| AC-15 to AC-18, AC-23 to AC-25 | integration; independent suite T22 | `test_audit_attribution.py`, `test_human_only_guard.py`, `test_access_events.py`, `test_q02_attribution_access_acceptance.py` |
| AC-19 to AC-22 | unit, integration; T52 (not built) | `unit/kernel/test_classification_flags.py`, `test_pii_scrubbing.py`, `agent_tests/test_gateway_pii_refusal.py` |
| AC-26 to AC-29 | integration; T27 | `test_audit_chain.py`, `test_q02t27_chain_independent.py` |
| AC-30 to AC-37 | integration, workflow replay; T36 | `test_retention_policies.py`, `test_retention_object_lock.py`, `test_legal_holds.py`, `backfill/test_q02t36_retention_and_holds.py` |
| AC-38, AC-39 | integration, unit, replay | `test_security_incidents.py`, `unit/platform/test_incident_clock.py` |
| AC-40, AC-41 | contract; T46 (not built) | `tests/contracts/compliance_kernel/` |
| AC-42, AC-43 | lint, generated security tests | `unit/quality/test_fresh_mfa_*.py`, `security/test_fresh_mfa_generated.py` |
| AC-44 | integration, unit, replay | `agent_tests/test_run_records.py`, `unit/agents/test_run_records.py`, `workflows/test_run_record_replay.py`; T46 (not built) |
| AC-45 | not built | Q-02-T45, T46 |
| AC-46 | generated security tests | `tests/security/` |

## 19. Rollout
- **Flags:** `agents.client_data_optin`, `compliance.legal_holds`, `compliance.incidents`, `compliance.firm_export` (rollout only; off answers 404 and the boundary keeps refusing). Never flagged: classification, attribution, the human-only guard, access events, the chain, floors, Object Lock classes, the hold check, shadow filtering.
- **Rollback:** each built part shipped with its own reversible migration; this spec changes no code.

## 20. Open questions
Status stays `draft` until these are answered; the builder approves (the row's acceptance).
- [ ] **Counsel (Q-02-T31, F-09-T38): the legal floor for each record type and service line**, with its authority and anchor. DEC-71 never defaults; the epic's §7.3 table is a starting list for counsel, not values.
- [ ] **Counsel (F-09-T58): Accrued's incident notice SLA to firms.** The code uses 72 hours from Accrued's confirmation (epic OQ-8); counsel confirms it in the DPA.
- [ ] **Counsel: the records the Safeguards disposal rule lets a firm keep beyond two years** (314.4(c)(6)) need a stated basis per record type; the basis column exists, its text is counsel's.
- [ ] **Ayush: the Brightwater Hale incident reference.** The register numbers incidents per firm in order (DEC-290), so a seed that records only INC-2026-005's facts gets INC-2026-001; canon also shows INC-2026-003 and -004 as closed, which no service can record yet. See TASK-1242 and DEC-363.
- [ ] **Ayush: the scheduled jobs.** Checkpoint, verify, anchor, retention-clock and partition schedules all wait for Temporal Schedule plumbing (Q-01-T26). Confirm they land before M7 or name the fallback (the epic's cut order keeps checkpoints and nightly verification).

## 21. Future / explicitly deferred
- Firm export live (Q-02-T43, T47), run records and the C6 v1 stub (Q-02-T41, T45), the MFA report and staff `amr` refusal (rest of Q-02-T37), the shadow report and QD-10 guard (Q-02-T50), Bedrock clearance (Q-02-T11, T12, T18, T28, T44), the independent suites T09, T46, T52, the rehearsal test (T48), the nightly hold reconciliation (DEC-229).
