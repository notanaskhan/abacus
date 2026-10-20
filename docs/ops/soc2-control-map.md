# SOC 2 control map (skeleton, Q-02-T01)

Maps the three Trust Services categories in scope (**Security**, **Availability**, **Confidentiality**; chapter 06 §5.7, DEC-26) to Accrued's controls. Every control cites at least one accepted ADR and an owner. Privacy and Processing Integrity are out of scope unless a customer asks.

Type I is as of Mon Mar 1, 2027; controls operate from Fri Dec 11, 2026 (gate tracker: [`compliance/README.md`](compliance/README.md)). This is a skeleton: the control statements and ADR links are fixed here; the compliance tool (Q-02-T10) holds the live evidence, and Q-02-T19 fills the M4 rows.

## How to read it

- **Criterion** is the Trust Services criterion the control helps meet (CC = common criteria, which make up Security; A = Availability; C = Confidentiality).
- **Owner** is `builder` for every control (solo amendment). Subservice organisations (the cloud provider, the identity vendor, the model route) are carved out and covered by vendor review under CC9.2, not owned here.
- **Evidence** is where the proof lives: a repo path (a path marked *planned* does not exist yet), or `tool: <integration>` for the compliance tool, or `vault` for documents that stay out of git.
- **Phase** is the gate by which the control must operate: `M4` (Fri Dec 11, 2026) or `M7` (Fri Apr 16, 2027).
- **State** is `designed` (an accepted ADR describes it), `building` (code or config in progress), `built` (code and tests exist; evidence not yet collected), or `operating` (evidence collected in the tool). Only the tool's evidence moves a row to `operating`.
- ADR-151 to ADR-154 are still `proposed`; every row that cites one also cites an accepted ADR. Re-check when they are accepted.
- Adding or changing a control: update the row and the ADR link in the same change; never edit an accepted ADR (write a new one).

## Security

| ID | Criterion | Control | ADRs | Owner | Evidence | Phase | State |
|---|---|---|---|---|---|---|---|
| SEC-01 | CC1.1 to CC1.5 | Security programme with a designated Qualified Individual, a written WISP, and defined accountability for each control | ADR-099, ADR-100 | builder | `compliance/README.md`; WISP (Q-02-T40, vault) | M4 | designed |
| SEC-02 | CC1.4, CC2.2 | Security training on joining and annually; acceptable-use and agent-session rules for the builder's workstation | ADR-099, ADR-084 | builder | tool: training; policies in tool | M4 | designed |
| SEC-03 | CC2.1, CC2.3 | Customers are told what to expect: status page, sub-processor and AI-provider list generated from the provider-terms register, breach-notification commitments | ADR-097, ADR-114 | builder | status page; `docs/operations/provider-terms.yaml` | M7 | designed |
| SEC-04 | CC3.1 to CC3.4 | Annual and per-change risk assessment, including the AI threat model and the exposure of a public repository | ADR-064, ADR-099 | builder | tool: risk assessment; `docs/architecture/ai-threat-model.md` | M4 | building |
| SEC-05 | CC3.2, CC4.1 | Living AI threat model reviewed whenever an agent, tool or data source is added | ADR-064, ADR-052 | builder | `docs/architecture/ai-threat-model.md` | M4 | building |
| SEC-06 | CC4.1, CC4.2 | Continuous monitoring: telemetry, dashboards, error tracking with content scrubbing, and alert definitions that must link an SLO or a runbook | ADR-022, ADR-094, ADR-093 | builder | `docs/ops/slos.md`; alarm definitions in `infra/` (planned) | M4 | designed |
| SEC-07 | CC4.1, CC7.1 | Evaluation suites run on prompt or model change and on a cadence; drift is a ticket | ADR-081, ADR-082, ADR-076 | builder | `evals/`; reports under `docs/operations/` | M7 | building |
| SEC-08 | CC5.1 to CC5.3 | Layered CI: five stages, with the security stage required on `main`; no skipped or weakened tests | ADR-083, ADR-077, ADR-080 | builder | ruleset export; CI history | M4 | building |
| SEC-09 | CC5.2 | Dependencies limited to an allowlist; supply-chain checks in CI (dependency review, pip-audit, Trivy) | ADR-083, ADR-057 | builder | `docs/architecture/dependency-allowlist.yaml`; CI | M4 | building |
| SEC-10 | CC6.1 | Authentication is bought, authorisation is in-house; sign-in through a managed identity provider with an enforced policy | ADR-020, ADR-029, ADR-030, ADR-141 | builder | tool: identity provider integration | M4 | building |
| SEC-11 | CC6.1, CC6.3 | Layered authorisation: tenancy, then ethical wall, then relationship, role and attribute; generated permission matrix tested role by action | ADR-023, ADR-026, ADR-027, ADR-147 | builder | `docs/architecture/permission-matrix.yaml`; `backend/tests/security/` (planned, Q-02-T13) | M4 | building |
| SEC-12 | CC6.1 | Tenant isolation: shared schema with forced row-level security; every query goes through a tenant session | ADR-014, ADR-002 | builder | `backend/tests/integration/test_tenancy.py`; generated isolation test (planned, Q-02-T13) | M4 | building |
| SEC-13 | CC6.2, CC6.3 | Access provisioned from a role catalogue and removed on departure; no standing staff access to firm data, with break-glass that is logged and time-limited | ADR-028, ADR-147, ADR-100 | builder | tool: access review | M4 | designed |
| SEC-14 | CC6.2, CC6.3 | Quarterly access review of cloud, repository, identity provider and tooling accounts | ADR-099, ADR-028 | builder | tool: access review (`make access-review`, planned) | M4 | designed |
| SEC-15 | CC6.1, CC6.6 | MFA for staff, and for client portal owners and signers; fresh MFA for sensitive actions | ADR-030, ADR-146 | builder | `make mfa-report` (planned, Q-02-T37) | M7 | building |
| SEC-16 | CC6.1, CC6.3 | Client access ladder and scoped grants; portal principals cannot reach firm routes | ADR-108, ADR-146, ADR-002 | builder | `backend/tests/security/test_route_introspection.py` (planned, Q-02-T15) | M7 | building |
| SEC-17 | CC6.4 | Physical and environmental security inherited from the cloud provider; the provider's own SOC 2 report is reviewed yearly | ADR-021, ADR-142 | builder | vault: provider report review | M4 | designed |
| SEC-18 | CC6.1, CC6.7 | Encryption in transit and at rest; client-side envelope encryption of evidence under a per-firm key | ADR-035, ADR-104, ADR-016 | builder | `backend/tests/unit/kernel/test_crypto.py` | M4 | built |
| SEC-19 | CC6.6 | Network boundary: private networking, edge protections and a restricted list of outbound hosts for workers; unauthenticated routes only from a fixed list | ADR-021, ADR-040, ADR-152 | builder | Terraform in `infra/`; route introspection test (planned, Q-02-T15) | M4 | building |
| SEC-20 | CC6.7 | Secrets and keys held in managed stores, never in git; secrets scan on every change | ADR-021, ADR-099 | builder | `backend/src/abacus_tools/quality/secrets_scan.py`; CI | M4 | built |
| SEC-21 | CC6.8 | Uploaded files are scanned before any parsing; parsing is isolated with size and time limits; formulas and macros are never executed | ADR-110, ADR-153 | builder | `backend/tests/unit/kernel/test_scanning.py` | M4 | built |
| SEC-22 | CC7.1 | Vulnerability management: dependency, container and static analysis in CI; findings ticketed with an owner and a due date | ADR-083, ADR-099 | builder | CI security stage; tool: vulnerability feed | M4 | building |
| SEC-23 | CC7.1, CC4.1 | Annual external penetration test and a retest of every critical and high finding; delta tests before each new real-data surface | ADR-099, ADR-080 | builder | vault: letter; tickets | M7 | designed |
| SEC-24 | CC7.2 | Anomaly detection and security alerting: AWS baseline detections, audit-chain mismatch alarm, cost anomaly job | ADR-099, ADR-094, ADR-007 | builder | alarms in `infra/` (planned) | M4 | designed |
| SEC-25 | CC7.2, CC7.3 | Append-only audit trail naming a person for every action; hash-chained checkpoints | ADR-007, ADR-018 | builder | `audit_events`; chain verification (planned, Q-02-T21) | M7 | building |
| SEC-26 | CC7.3 to CC7.5 | Incident response: severities, kill switches, contain-preserve-assess-notify, blameless review whose actions become tests, lint rules, alerts or ADRs | ADR-097, ADR-098 | builder | `docs/runbooks/README.md`; tool: incident register | M4 | designed |
| SEC-27 | CC7.4, CC9.1 | Runbooks for each failure scenario, linked from alerts, rehearsed, with last-rehearsed dates | ADR-098 | builder | `docs/runbooks/README.md` | M4 | building |
| SEC-28 | CC8.1 | Change management: pull request, required checks, build once and promote the same artefact, workflow-safe deploys, staged migrations | ADR-083, ADR-088, ADR-090, ADR-091 | builder | ruleset export; release manifests (planned) | M4 | building |
| SEC-29 | CC8.1 | Feature flags with an owner and an expiry; an expired flag fails the fast check | ADR-089, ADR-105, ADR-151 | builder | `docs/architecture/feature-flags.yaml` | M4 | built |
| SEC-30 | CC8.1 | Protected paths: policy files, the permission matrix, migrations on `main` and generated files are not hand-edited by agents | ADR-027, ADR-135 | builder | `docs/architecture/protected-paths.md` | M4 | built |
| SEC-31 | CC8.1 | Agents propose and a named person decides; the identity of the model behind each change is recorded | ADR-005, ADR-084, ADR-086 | builder | PR records; human-only guard (planned, Q-02-T17) | M4 | building |
| SEC-32 | CC6.1, CC6.7 | Model data boundary: client data reaches only an approved route in our cloud account, with a current provider-terms entry, firm opt-in, a cleared agent, and no failover to another route | ADR-113, ADR-114, ADR-115 | builder | `backend/tests/unit/ai_gateway/test_client_data_boundary.py` | M7 | built |
| SEC-33 | CC6.1, CC7.2 | Hostile client content: every client or client-system string is untrusted; delimited blocks, schema-constrained output, sanitised plain-text rendering | ADR-052, ADR-064, ADR-065 | builder | `backend/tests/unit/ai_gateway/test_context_builder.py`; `evals/screening/suite.yaml` | M4 | built |
| SEC-34 | CC9.1 | Business disruption: founder dependency plan, busy-season readiness, backup and recovery | ADR-100, ADR-075, ADR-096 | builder | `docs/ops/compliance/README.md` | M4 | designed |
| SEC-35 | CC9.2 | Vendor and sub-processor management: register with review dates, vendor review before use, subprocessor list generated from the register | ADR-114, ADR-154, ADR-113 | builder | `docs/ops/vendors/README.md`; register | M4 | building |

## Availability

| ID | Criterion | Control | ADRs | Owner | Evidence | Phase | State |
|---|---|---|---|---|---|---|---|
| AVL-01 | A1.1 | Reliability targets (availability, latency, freshness, durability) defined as SLOs with burn-rate alerts; an exhausted budget pauses feature work | ADR-093 | builder | `docs/ops/slos.md`; alarms in `infra/` (planned) | M4 | designed |
| AVL-02 | A1.1 | Capacity management: work classes, fair-share rate limits, admission control and graceful degradation under provider limits | ADR-043, ADR-071, ADR-072 | builder | `backend/tests/integration/test_work_class_queues.py` | M4 | built |
| AVL-03 | A1.1 | Per-firm and platform budgets cap AI spend; a cost anomaly job alerts | ADR-069, ADR-070 | builder | `backend/tests/integration/agent_tests/test_gateway_call.py` | M4 | built |
| AVL-04 | A1.1 | Busy-season readiness test before each tax window; change policy from the first real firm's go-live | ADR-075, ADR-092, ADR-151 | builder | RB-16 (planned) | M7 | designed |
| AVL-05 | A1.2 | Multi-zone database with point-in-time recovery; encrypted backup copies in a second US region; versioned, write-once evidence replicated to a second region | ADR-096, ADR-016, ADR-021, ADR-142 | builder | Terraform in `infra/`; tool: AWS integration | M4 | building |
| AVL-06 | A1.2 | Environments, build-once promotion and rollback keep a bad release from taking production down | ADR-087, ADR-088, ADR-090 | builder | deploy history | M4 | building |
| AVL-07 | A1.3 | Quarterly restore drill into an isolated environment, verifying control totals and evidence fingerprints; yearly regional-failover tabletop | ADR-096, ADR-098 | builder | tool: drill record; RB-10, RB-11, RB-15 | M4 | designed |
| AVL-08 | A1.3 | Continuous integrity sweep re-fingerprints stored evidence and verifies the audit chain nightly | ADR-096, ADR-004 | builder | nightly run history (planned, Q-02-T21) | M7 | building |
| AVL-09 | A1.1, A1.2 | Synthetic canary firm runs the end-to-end flow every 15 minutes and pages on two consecutive failures | ADR-094, ADR-093 | builder | canary run history | M4 | designed |

## Confidentiality

| ID | Criterion | Control | ADRs | Owner | Evidence | Phase | State |
|---|---|---|---|---|---|---|---|
| CON-01 | C1.1 | Data classification: every model field carries a level; logging, error tracking, exports and the AI gateway read the same tags | ADR-031 | builder | `backend/tests/unit/kernel/test_classification.py` | M4 | built |
| CON-02 | C1.1 | Need-to-know: metadata is visible more widely than content; ethical walls hide a walled client entirely | ADR-024, ADR-026 | builder | `backend/tests/integration/agent_tests/test_walls_enforcement.py` | M4 | built |
| CON-03 | C1.1 | The firm owns its client records; the firm sets who sees what | ADR-001, ADR-006 | builder | contract terms (vault) | M7 | designed |
| CON-04 | C1.1 | Restricted data never appears in logs, traces, error reports or metrics; export attributes are allowlisted | ADR-031, ADR-022 | builder | `backend/tests/unit/kernel/test_telemetry_scrubbing.py` | M4 | built |
| CON-05 | C1.1 | Tenant-scoped caches and memory: no reuse of results, prompts, examples or learning across firms | ADR-067, ADR-053, ADR-068 | builder | test gap noted in `docs/architecture/ai-threat-model.md` | M7 | designed |
| CON-06 | C1.1 | AI provider terms: zero training, no retention beyond processing, US region; only an approved route carries client data | ADR-113, ADR-114, ADR-115 | builder | `docs/operations/provider-terms.yaml` | M7 | building |
| CON-07 | C1.1 | Per-firm encryption keys; connector credentials under envelope encryption | ADR-035, ADR-104 | builder | `backend/tests/unit/kernel/test_crypto.py` | M4 | built |
| CON-08 | C1.2 | Retention by record type and service line, legal holds that block destruction, and destruction that is approved | ADR-032, ADR-033 | builder | retention floors (planned, Q-02-T23, Q-02-T29) | M7 | building |
| CON-09 | C1.2 | Offboarding returns the firm's data (engagement export) and crypto-shreds its keys, including in backups | ADR-034, ADR-036, ADR-035 | builder | RB-13 (planned) | M7 | designed |
| CON-10 | C1.1 | Evidence is immutable and versioned; write-once storage prevents alteration | ADR-004, ADR-016 | builder | `backend/tests/integration/test_evidence_storage.py` | M4 | built |

## Cross-checks (to run before the Type I as-of date)

1. Every `ADR-nnn` above exists in `docs/adr/`, and every row cites at least one that is `accepted`.
2. Every repo path in the Evidence column exists, or is marked *planned* with a task id.
3. Every M4 row has evidence in the tool dated on or before Fri Dec 11, 2026.
4. No row names a vendor, a person, an amount or an account.
