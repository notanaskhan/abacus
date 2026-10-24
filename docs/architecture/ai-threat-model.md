# AI threat model (ADR-064)

A living model of how the Accrued Agent and its data paths can be attacked or can go wrong, and what stops each case. ADR-064 requires it to be reviewed whenever an agent, a tool or a data source is added, and to treat every string that comes from a client or a client system as untrusted. First version: Tue Oct 20, 2026 (Q-02-T02). Refreshed Sat Oct 24, 2026 for pen test #1 (Q-03-T018): the scope section, the sign-in, portal, evidence, compliance-record and outbound rows, and coverage updated to what `main` holds. A second pass on the same day, after the S7 batch merged (TASK-1178), added what S5–S7 built. That covers the gateway TIN refusal (ADR-167), portal sessions and MFA (ADR-168), invitations v2, the incident register, G2 v2 and the viewer. It also adds the client upload policy decided that day, which is described as the intended control because it is still being built. Companion decisions: ADR-052 (hostile client content), ADR-065 (output controls), ADR-113 to ADR-115 (the data boundary).

## How to use this file

- **Adding an agent, a tool, a data source or a route:** add or update the rows it touches in the same change, and tick the checklist at the end. ADR-064 says the pull-request checklist requires this; `.github/pull_request_template.md` does not carry the item yet, so copy the checklist by hand until it does.
- **Coverage column.** Every threat row names where its mitigation is proven, one of:
  - **Tested**: an existing test or evaluation suite (a path that exists today).
  - **Planned**: a task id from the plan (`Q-02-Tnn`) that will add the test or control.
  - **ADR**: the rule is decided in an accepted ADR; no test names it yet. Each such row is also listed under *Gaps*.
- Evaluation suites (`evals/`) call real models and carry thresholds that are never lowered. A row that cites one relies on the suite's `adversarial_containment` or `injection_resistance` metric staying at 1.0.
- This file holds no client data, no prompts' full text, no secrets and no names of firms or people.

## Pen test #1 scope (refreshed 2026-10-24, Q-03-T018; second pass after the S7 batch)

Pen test #1 runs Feb 15 – Mar 5, 2027 on the pinned staging build (Q-02-T35), with highs retested closed by Apr 9. This table names every surface in scope and what is built on `main` today, so the tester and the triage (Q-02-T42) start from the same map. "Built" means live routes with tests; "stub" means a contract stub behind its flag; "not built" means out of the build. Synthetic tenants and synthetic data only; testers get synthetic accounts, never real firm or taxpayer data. This file carries no exploit detail, credentials or environment addresses; those stay in the engagement letter and the vault.

| Surface | Built on main | Boundaries | Rows |
|---|---|---|---|
| Staff sign-in: hosted AuthKit, the session BFF (`/v1/auth/*`), refresh rotation and reuse detection, step-up for fresh-MFA actions, 30-minute idle and 12-hour absolute limits (DEC-140) | built (P-01-T09, ADR-165) | TB2 | AU-01 to AU-04, AU-09 |
| Portal sign-in by emailed code, portal sessions pinned to tenant and host, lockout, the MFA floor, trusted devices and backup codes | built (P-08-T10, P-08-T17; ADR-168, DEC-34) | TB2 | AU-05 to AU-08, AU-10 |
| Client invitations v2: the no-oracle preview, sign-in for a pending invitee, acceptance with template grants, terms and inviter attribution | built (P-08-T18, DEC-275, DEC-35's 14-day single-use links) | TB2 | IN-01 to IN-04 |
| Portal hosts and branding: host-to-firm resolution, Public-only branding, logo re-encoding | built for platform-provisioned hosts under the portal base domain (P-08-T05, ADR-163). A firm's own custom domain and its certificate are **not built** (P-11; RB-21) | TB2 | PO-01, PO-02 |
| Portal reads and the role union: home, binders, request items, scoped grants (owner, taxpayer, third party) | built for home (P-08-T13) and the grant model (ADR-146); the PBC section (POR-03/04/14) is a **stub** in fixture mode (R-01-T01) | TB2 | CT-08, PO-03 |
| Uploads: firm uploads, the portal drop, scanning, parsing, previews | firm uploads built (ADR-110, ADR-153); the policy decided 2026-10-24 (50 MB, content-sniffed allowlist with a matching extension, active content refused or held) is **being built**, so ED-018 to ED-021 are open; the portal drop route is a **stub** (413 and 415 declared, R-01-T01) | TB1 | HC-07, HC-08, EV-01, EV-06 |
| Evidence, citations and the viewer: citation v2 verifiers, page images, the C4 viewer (manifest, pages, regions, search) | verifiers and `record_citations` built (P-03-T06); the viewer routes built behind `evidence.viewer_v1` (P-03-T09). Until masking lands (P-03-T13, T15) no masked rendition exists, so every page answers 409 `preview_outdated` (DEC-266) | TB5, TB7 | HC-11, EV-02 to EV-05 |
| Identifiers: TIN storage and reveal; TINs in model context, logs and telemetry | built (P-07-T10): sealed values, masked by default, reveal with fresh MFA and a reason, one audit row. The gateway refuses an unmasked TIN in any context part, and logs, error reports and metrics mask TIN patterns (Q-02-T32, ADR-167 §1–§2). The consent gate (§3) is T-01's and not built | TB3, TB7, TB8 | TRI-01, TRI-03, TRI-05 |
| Independence (G2 v2): assignment, sign-off and client-facing actions on attest clients | built (P-07-T24, ADR-164); the `g2_blocks_view` setting can only tighten | TB2 | G2-01, G2-02 |
| Agent runs: list, trace, trace export | built (C6 v0, SPEC-318) | TB7, TB8 | CR-04 |
| Legal holds | built behind `compliance.legal_holds` (Q-02-T29) | TB2 | CR-01 |
| Incident register and staff propagation | built behind `compliance.incidents` (Q-02-T33, in the S7 batch) | TB2 | CR-02, CR-05 |
| Firm data export (dual approval, link) | **not built** (Q-02-T43, S10); rows are in the matrix only | TB8 | CR-03 |
| Follow-ups and notification email | built (P-06-T14 follow-ups sent by a person after Undo; C16 email behind `notifications.email`) | TB7 | OB-01, OB-02 |
| The gateway and the four specialists | built; real data stays off for every firm until clearance (ADR-113 to ADR-115) | TB3 to TB6 | HC-, TL-, DB- rows |

## What is being protected: assets

| ID | Asset | Class (ADR-031) | Why it matters |
|---|---|---|---|
| AS-01 | Client financial data: trial balances, ledger rows, uploaded evidence, request responses, messages | Restricted | The firm's duty of confidentiality; the reason firms buy the product |
| AS-02 | Tax return information (TRI) and direct identifiers (taxpayer identification numbers, names tied to returns) | Restricted, with extra flags planned (Q-02-T25, Q-02-T32) | Statutory consent and disclosure rules; breach-notification duties |
| AS-03 | Health-plan participant data that can appear in benefit-plan audits (PHI) | Restricted, flag planned (Q-02-T25) | Business-associate posture; added breach duties |
| AS-04 | Tenant boundary: one firm never sees, affects or learns from another | n/a | A single cross-firm exposure is a SEV1 (ADR-097) |
| AS-05 | Per-firm encryption keys and connector credentials | Restricted | Compromise opens one firm's evidence and its client systems |
| AS-06 | Integrity of decisions: what a person accepted, waived or signed, and the audit trail behind it | Confidential | Agents propose, named humans decide (ADR-005); a forged or silent decision destroys the audit value |
| AS-07 | Evidence immutability and citations | Restricted | A changed or invented source defeats the product's reason to exist (ADR-004, ADR-066) |
| AS-08 | Firm knowledge: methodology, approved rules, corrections, examples | Confidential | Poisoned or leaked knowledge changes future work or helps a competitor (ADR-053, ADR-068) |
| AS-09 | The provider-terms register and the route configuration | Internal, protected | They decide which model routes may carry client data (ADR-114) |
| AS-10 | Prompts, the prompt registry and evaluation baselines | Internal | An unreviewed prompt or a lowered threshold silently weakens every defence |
| AS-11 | Capacity and budget: model quota, per-firm and platform AI spend | Internal | Exhaustion is an availability and cost attack (ADR-069 to ADR-072) |
| AS-12 | What clients see: messages, requests and portal content | Confidential | Model-written text to a firm's clients is held off until the data boundary lifts (ADR-111) |

## Who attacks, and what can go wrong without an attacker

| ID | Actor | Capability |
|---|---|---|
| ACT-A | Hostile or careless client contact, or a client's counterparty | Writes any file, email, request response or comment the product ingests |
| ACT-B | Compromised or manipulated client system | Controls every field a connector returns: account names, vendor and customer names, memos, descriptions |
| ACT-C | Another firm (a tenant) | Holds a valid account on the same platform; probes for cross-tenant reads, cache reuse or shared state |
| ACT-D | Firm staff acting beyond their remit | A walled-off person, or someone without access to a client, using an agent as a proxy |
| ACT-E | Client portal user | Valid portal session scoped to one client; tries other clients, other firms or firm routes |
| ACT-F | The model itself | Not malicious: wrong arithmetic, invented citations, over-confident output, following instructions it should treat as data |
| ACT-G | A model provider or sub-processor | Retains, trains on, or exposes data under terms we did not approve |
| ACT-H | Supply chain | A dependency or tool that reads prompts, credentials or data |
| ACT-I | An Accrued account or workstation that is compromised | Operator access to production, or the builder's own agent sessions |

## Data path and trust boundaries

```
 client / client system ──TB1──▶ ingest (scan, parse, store, classify)
                                     │
 portal user ───────────────TB2────▶ API (authorise, visible, walls)
                                     │
                         context builder ──TB3──▶ ai_gateway ──TB4──▶ model route
                         (untrusted blocks)      (boundary, limits,   (approved cloud route
                                                  PII refusal, log)    or synthetic-only route)
                                     ▲                                    │
                                     └──── schema check, citation check ◀─┘ TB5
                                     │
                    agent run ──TB6──▶ tool layer (narrow typed tools, intersected permissions)
                                     │
                    results ──TB7──▶ firm users (shadow filter, plain text)  /  clients (deterministic templates only)
                                     │
                    telemetry, logs, exports ──TB8──▶ shared tooling (scrubbed)
```

| ID | Boundary | What crosses | Rule that holds it |
|---|---|---|---|
| TB1 | Client or client system into the platform | Uploads, email, connector fields, request responses, comments | Everything is hostile (ADR-052, ADR-064); scan before parsing, isolated parsing, formulas never run (ADR-110); connectors read only (ADR-040) |
| TB2 | Portal into the API | Portal requests with a client-scoped session | Scoped grants and the client access ladder (ADR-108, ADR-146); portal principals reach no firm routes; portal host pinned to the session's tenant |
| TB3 | Context builder into the gateway | The assembled prompt and its untrusted blocks | Spec-named untrusted fields go in labelled, JSON-encoded blocks; raw ledger data never reaches a model (ADR-050, ADR-051); direct identifiers refused (planned, Q-02-T32) |
| TB4 | Gateway to the model route | The call and the client data in it | Bedrock inside our cloud account, US region, no global profile; a current register entry; firm opt-in; cleared agent; stage; no exclusion; no failover for real firms (ADR-113 to ADR-115) |
| TB5 | Model output back into the platform | Text, structured fields, citations | Schema-constrained output; quotes verified against the source; plain-text sanitising with links stripped (ADR-065, ADR-066) |
| TB6 | Agent into the tool layer | Tool calls | Narrow typed tools; permissions are the intersection of agent role, initiator and task scope; the model never decides permissions; no decision actions in agent contexts (ADR-005, ADR-025, ADR-049) |
| TB7 | Platform out to people | Agent results to firm users; messages to clients | Shadow-stage output hidden from firm reads; agent text only through the sanitising component; no model-written text to clients (ADR-111) |
| TB8 | Platform out to shared tooling | Logs, traces, error reports, metrics, usage records | Allowlisted attributes only; classification tags drive scrubbing; usage records hold hashes and counts, not content (ADR-031, ADR-022) |

## Threats and mitigations

### Hostile content and prompt injection

| ID | Boundary | Threat | Mitigation | Coverage |
|---|---|---|---|---|
| HC-01 | TB1, TB3 | Instructions inside an uploaded document (visible, hidden or white-on-white) tell the screener or upload reviewer to mark it ready or to ignore a flaw | The document is the only untrusted field and sits in a labelled block; the prompt treats blocks as data; output is schema-constrained and only proposes (ADR-052, ADR-005) | Tested: `backend/tests/unit/agents/test_upload_reviewer.py`, `backend/tests/unit/ai_gateway/test_prompt_registry.py`, `evals/upload_review/suite.yaml`, `evals/screening/suite.yaml` |
| HC-02 | TB1, TB3 | Instructions in connector fields (account names, vendor names, memos) reach the screener or another agent | The boundary covers ledger fields, not only uploads (ADR-064); fields named in the agent spec render only inside untrusted blocks | Tested: `backend/tests/integration/agent_tests/test_screening.py`. Planned: Q-02-T26 (adversarial account names in the screener suite) |
| HC-03 | TB1, TB3 | Instructions in an inbound email or attachment steer the matcher | The document alone is untrusted; candidates are references; the matcher only proposes | Tested: `backend/tests/unit/agents/test_matcher.py`, `evals/matching/suite.yaml` |
| HC-04 | TB1, TB3 | Client-written text (request descriptions, comments, responses) steers the guidance drafter or entry assessor | Item text and examples are the only untrusted fields; containment needs the item delimited | Tested: `backend/tests/unit/agents/test_guidance_drafter.py`, `backend/tests/unit/agents/test_entry_assessor.py`, `evals/guidance_drafting/suite.yaml`, `evals/entry_assessment/suite.yaml` |
| HC-05 | TB3 | Content contains the closing delimiter, or a fake trusted field, to break out of its block | Untrusted values are JSON-encoded with `<` escaped; a hostile key cannot become a field | Tested: `backend/tests/unit/ai_gateway/test_context_builder.py`, `backend/tests/unit/tools/evals/test_evals.py` |
| HC-06 | TB1, TB5 | Zero-width characters, compatibility forms or lookalike names defeat quote verification or entity matching | Quotes are normalised before verification; suites carry deception and lookalike cases | Tested: `backend/tests/unit/agents/test_upload_reviewer.py`, `evals/screening/suite.yaml` |
| HC-07 | TB1 | Spreadsheet formulas or macros run in the parser or the preview | Formulas are never evaluated, only cached values; macros ignored; previews are server-made images | Tested: `backend/tests/unit/evidence/test_extraction.py`, `backend/tests/unit/connections/test_import_parse.py`, `backend/tests/unit/synthetic/test_adversarial.py` |
| HC-08 | TB1 | Malware, archive bombs or parser exploits in an upload | Malware scan before any parsing, fail closed outside synthetic environments; isolated worker with limits (ADR-110, ADR-153) | Tested: `backend/tests/unit/kernel/test_scanning.py`. Planned: Q-02-T35, Q-02-T42 (pen test #1 covers the upload pipeline) |
| HC-09 | TB3 | Oversized or crafted fields exhaust the context or the budget | Per-layer token budgets with recorded truncation; lists over the row limit refused; budget refused before the provider is called | Tested: `backend/tests/unit/ai_gateway/test_context_builder.py`, `backend/tests/integration/agent_tests/test_gateway_call.py`, `evals/screening/suite.yaml` |
| HC-10 | TB5, TB7 | Model text carries an outbound link, image beacon or markup that leaks data when rendered | Links to hosts outside an allowlist (empty by default) become a placeholder; the front end renders agent text only through a plain-text component (ADR-065) | Tested: `apps/web/src/agent-text.test.tsx`, `apps/web/src/lint/eslint-rules.test.ts`. ADR: ADR-065 for the server-side sanitiser, which has no backend test (see Gaps) |
| HC-11 | TB5 | A made-up or altered quotation is accepted as evidence | Citations are structured; each quote is checked against the page or cell it names; the firm sees only verified quotes (ADR-066) | Tested: `backend/tests/unit/agents/test_upload_reviewer.py`, `backend/tests/unit/agents/test_agent_citations.py`; suites hold `citation_verification` at 1.0 |
| HC-12 | TB5 | The model does arithmetic on financial data and gets it wrong | Code computes, the model judges; totals are summed from line rows in code; raw ledger lists over the row limit never reach a model (ADR-050) | Tested: `backend/tests/unit/agents/test_agent_citations.py`, `backend/tests/unit/ai_gateway/test_context_builder.py` |

### Tool layer and agency

| ID | Boundary | Threat | Mitigation | Coverage |
|---|---|---|---|---|
| TL-01 | TB6 | An injected instruction persuades an agent to accept, reject, waive, mark not-applicable or send | Agent contexts never hold decision actions; the action is refused at the role layer; a database trigger will refuse agent and policy actors on the human-only list | Tested: `backend/tests/integration/agent_tests/test_agent_authz.py`, `backend/tests/integration/test_human_only_guard.py` (the database refuses listed actions from agent and policy actors). Planned: Q-02-T22 (independent tests) |
| TL-02 | TB6 | Confused deputy: an agent reaches data its initiator may not see | Effective permission is the intersection of agent role, initiator and task scope; unknown, revoked or other-firm initiators get no context | Tested: `backend/tests/integration/agent_tests/test_agent_authz.py`, `backend/tests/unit/identity/test_firm_level_agent.py` |
| TL-03 | TB6 | An agent keeps running for someone who has since been walled off from the client | The wall is checked before relationship, role and attribute, at every stage; a walled run fails non-retryably; walls answer 404 | Tested: `backend/tests/integration/agent_tests/test_walls_runs.py`, `backend/tests/unit/identity/test_ethical_walls.py` |
| TL-04 | TB6 | Injected instructions drive a generic tool: arbitrary query, URL fetch or file read | No generic query, HTTP or file tools; tools are named for intent with typed inputs and outputs; no agent framework (ADR-049, ADR-057) | Tested: `backend/tests/unit/quality/test_banned_patterns_agents.py` (static rules for agent code). ADR: ADR-049 |
| TL-05 | TB1, TB6 | A connector writes to a client's system | Connector clients have read methods only; worker outbound hosts restricted; a conformance test fails any non-read request (ADR-040) | Tested: `backend/tests/unit/connections/test_fake_conformance.py` |
| TL-06 | TB7 | An agent sends or schedules client-facing messages beyond the firm's autonomy policy | Autonomy conditions bound by declared scope and initiator; client-visible pre-checks are deterministic templates; no model text to clients (ADR-111) | Tested: `backend/tests/unit/identity/test_autonomy_condition.py`, `backend/tests/unit/communications/test_invitation_wording.py`. Planned: Q-02-T08, Q-02-T09 (no model text to clients) |
| TL-07 | TB7 | An outbound message names clients, entities, accounts or amounts outside the engagement | Scope checker in the send path blocks and flags (ADR-065); today only deterministic templates are sent (ADR-111) | ADR: ADR-065, ADR-111. No scope-checker test yet (see Gaps) |
| TL-08 | TB6, TB7 | An agent action is attributed to "the agent" with no named person, so no one is accountable | Every action names a person, "person via Agent", or the system for scheduled work; delegation chain recorded (ADR-007, ADR-025) | Tested: `backend/tests/integration/test_audit_attribution.py`, `backend/tests/integration/test_q02_attribution_access_acceptance.py`. Planned: Q-02-T22 (independent tests for each actor kind) |
| TL-09 | TB6 | Learning-loop poisoning: hostile content becomes an example or a firm rule | Corrections become examples at once but firm rules only after manager approval and a passing evaluation; rules are versioned and reversible (ADR-068) | ADR: ADR-068, ADR-053. No test yet (see Gaps) |
| TL-10 | TB3 | A prompt or model is changed without evaluation, or a cheaper tier is used where it is not eligible | Versioned, immutable prompt registry; tier eligibility is keyed to the agent's own suite and fails closed; evaluations run on prompt or model change (ADR-074, ADR-081) | Tested: `backend/tests/unit/ai_gateway/test_prompt_registry.py`, `backend/tests/unit/ai_gateway/test_tier_eligibility.py` |
| TL-11 | TB3, TB4 | Denial of wallet: bulk hostile uploads run up cost or starve other firms | Per-firm and platform budgets; work classes with fair share; admission control degrades instead of failing silently (ADR-069, ADR-071, ADR-072) | Tested: `backend/tests/integration/agent_tests/test_gateway_call.py`, `backend/tests/integration/test_work_class_queues.py` |

### Cross-tenant exposure

| ID | Boundary | Threat | Mitigation | Coverage |
|---|---|---|---|---|
| CT-01 | TB2, TB3 | A query without tenant scope feeds another firm's rows into a response or a prompt | Shared schema with forced row-level security; every query in a tenant session; no tenant means no rows | Tested: `backend/tests/integration/test_tenancy.py`, `backend/tests/security/test_tenant_isolation.py` (generated over every tenant table) |
| CT-02 | TB6 | An agent context is issued for a user of another firm | Context issuance checks firm membership; other-firm initiators get nothing; denial at the tenancy layer comes first | Tested: `backend/tests/integration/agent_tests/test_agent_authz.py` |
| CT-03 | TB3, TB4 | Prompt caches, result reuse or few-shot retrieval share state across firms | Caching keys, result reuse and example retrieval are scoped to one firm; identical inputs from two firms are separate runs (ADR-067) | ADR: ADR-067. No test yet (see Gaps) |
| CT-04 | TB3 | Memory, knowledge retrieval or embeddings return another firm's content | Retrieval goes through `visible()`; memory scoped to firm, client or engagement; no learning across firms (ADR-053) | Planned: Q-02-T13 (covers every registered table, including embedding tables). ADR: ADR-053 |
| CT-05 | TB8 | Client content reaches shared logs, traces, error reports or metrics | Only allowlisted span attributes are exported; exception events are never exported; classification tags drive scrubbing | Tested: `backend/tests/unit/kernel/test_telemetry_scrubbing.py`, `backend/tests/unit/kernel/test_classification.py`, `backend/tests/unit/quality/test_banned_patterns_logging.py` |
| CT-06 | TB8 | Usage records or events keep the prompt or the model output | Usage records carry a hash of the inputs and counts; never the output or the context | Tested: `backend/tests/integration/agent_tests/test_gateway_call.py` |
| CT-07 | TB4 | A provider keeps or trains on one firm's data, exposing it to others | Zero training and no retention beyond processing are conditions of a register entry; a counsel second approver is added before real data (ADR-114) | Tested: `backend/tests/unit/tools/test_client_data_clearance.py`. Planned: Q-02-T18, Q-02-T52 |
| CT-08 | TB2 | A portal user reaches another client's items, another firm's data, or a firm route | Client-scoped grants; client roles only respond; one matrix action per route; portal host pinned to the session's tenant | Tested: `backend/tests/unit/requests/test_client_responses.py`, `backend/tests/security/test_route_introspection.py` (one action per route), `backend/tests/security/test_permission_matrix_generated.py`, `backend/tests/integration/test_portal_sign_in.py` (a portal token works only on its own host). Planned: Q-02-T35, Q-02-T42 (pen test #1). ADR: ADR-108, ADR-146, ADR-168 |
| CT-09 | TB8 | Event streams carry record content to a client that should not have it | Events carry identifiers only; the client fetches content through authorised routes | ADR: ADR-024. The real-time channel is not built; its pen test is scheduled for Nov 2027 (chapter 06 §5.6). Test to be added when it ships (see Gaps) |
| CT-10 | TB1 | A firm's key or connector credential is compromised and opens its evidence | Per-firm keys; envelope encryption with the firm id bound as associated data; rotation runbook; destroying the key shreds the data | Tested: `backend/tests/unit/kernel/test_crypto.py`. ADR: ADR-035, ADR-104 |

### Data boundary and model route

| ID | Boundary | Threat | Mitigation | Coverage |
|---|---|---|---|---|
| DB-01 | TB4 | A real firm's data is sent to the direct API or any unapproved route, including by failover when the approved route is down | Client data uses the approved cloud route only; the direct route is for synthetic data and evaluations; outage degrades and queues, never reroutes (ADR-113) | Tested: `backend/tests/unit/ai_gateway/test_client_data_boundary.py`, `backend/tests/unit/ai_gateway/test_data_boundary.py`, `backend/tests/unit/kernel/test_client_data_settings.py`, `backend/tests/unit/kernel/test_model_data_boundary_settings.py` |
| DB-02 | TB4 | A global inference profile is used and processing leaves the United States | Only in-region or US geography profiles; configuration validation rejects global profiles (ADR-113) | Planned: Q-02-T11 (route configuration on staging; add the check there). ADR: ADR-113. No test names the global profile yet (see Gaps) |
| DB-03 | TB4 | The register has no entry for the route, or the entry is past its review date | Settings refuse client data without a current entry; at boot a past-due entry switches client data off for that route (ADR-114) | Tested: `backend/tests/unit/kernel/test_client_data_settings.py`, `backend/tests/unit/tools/test_client_data_clearance.py`. Planned: Q-02-T18 (second approver, boot validation) |
| DB-04 | TB4 | An agent without a passing Bedrock evaluation and parity report processes real data | The agent spec must say `client_data: cleared`, which needs both reports; none is cleared yet | Tested: `backend/tests/unit/tools/test_client_data_clearance.py`. Planned: Q-02-T44 |
| DB-05 | TB4 | An engagement its partner excluded is still processed | Exclusion refuses every route for every firm, audited and counted | Tested: `backend/tests/unit/ai_gateway/test_client_data_boundary.py` |
| DB-06 | TB7 | Shadow-stage output is shown to firm users or clients before it is validated | Shadow output is recorded and hidden on every firm-facing read; the first stage is always shadow; only a platform action promotes | Tested: `backend/tests/unit/agents/test_agent_stages.py`. Planned: Q-02-T08, Q-02-T09, Q-02-T48 |
| DB-07 | TB4 | A firm has not opted in, or opted in against an older disclosure | Opt-in is checked in the gateway before any network call; a material change to the terms needs a new opt-in (ADR-114, ADR-115) | Tested: `backend/tests/unit/ai_gateway/test_client_data_boundary.py`. Planned: Q-02-T07, Q-02-T08 |

### Tax return information and personal data

| ID | Boundary | Threat | Mitigation | Coverage |
|---|---|---|---|---|
| TRI-01 | TB3 | A taxpayer identification number or similar identifier appears in model context | The gateway scans the system prompt and every context part before anything else, on every route including `fake`. An unmasked TIN that passes the SSN, ITIN or EIN rules is refused as `pii_in_context` before any budget read or network call. The refusal is audited with indices only and never retried or rerouted. Fields carry `pii_kind`, and masking has one helper (ADR-167 §1–§2, DEC-295) | Tested: `backend/tests/unit/ai_gateway/test_pii_in_context.py` (every part, property tests, the log line names no value), `backend/tests/unit/kernel/test_tin_patterns.py`, `backend/tests/unit/kernel/test_classification_flags.py`. Planned: Q-02-T52 (independent tests) |
| TRI-02 | TB4 | Tax return information is processed without the taxpayer's consent, or on a route whose terms do not cover it | Consent-gate shape agreed before the tax epic builds it; the route and register rules apply first; tax work is not in the real-data scope before the tax pilot gate | Planned: Q-02-T25 (consent-gate shape), RB-17 in `docs/runbooks/README.md`. ADR: ADR-113, ADR-114 |
| TRI-03 | TB8 | Tax return information or health-plan data lands in logs, exports or error reports | Classification flags (`tri`, `phi`, `pii_kind`) are allowed on Restricted only; logs refuse models with Restricted fields and mask TIN patterns in every string; error events and metric attributes mask them too (ADR-167) | Tested: `backend/tests/unit/kernel/test_classification.py`, `backend/tests/unit/kernel/test_telemetry_scrubbing.py`, `backend/tests/unit/kernel/test_pii_scrubbing.py` (one log line, one error event, one metric attribute) |
| TRI-04 | TB4 | Health-plan participant data reaches a vendor without a business-associate posture | A `phi` flag on fields (built, ADR-167); posture documented in the diligence pack before real data | Tested: `backend/tests/unit/kernel/test_classification_flags.py` (the flag). Planned: Q-02-T49 (diligence pack). ADR: ADR-031, ADR-167 |
| TRI-05 | TB7 | An identifier is revealed to a user with no record of who looked | Masked by default; reveal logged as an access event | Tested: `backend/tests/integration/test_tin_reveal.py` (one audit row, no log line, offshore refused, `no-store`), `backend/tests/integration/test_access_events.py` |

### Supply chain and platform

| ID | Boundary | Threat | Mitigation | Coverage |
|---|---|---|---|---|
| SC-01 | all | A dependency or agent framework reads prompts or credentials | No orchestration framework; dependency allowlist; dependency review and audit in CI (ADR-057, ADR-083) | Tested: `backend/tests/unit/quality/test_check_dependencies.py` |
| SC-02 | TB3, TB4 | Code calls a provider directly and skips the gateway's controls | Provider SDKs import only inside the gateway; every provider call is preceded by the boundary check (ADR-019) | Tested: `backend/tests/unit/ai_gateway/test_data_boundary.py` |
| SC-03 | all | A secret or real client data is committed to the public repository (prompts, fixtures, test data) | Secrets scan on every change; synthetic data only until the real-data gate (ADR-085) | Tested: `backend/tests/unit/quality/test_secrets_scan.py` |
| SC-04 | TB6 | The builder's own agent session is steered by hostile text in a repository file or tool output | Agent sessions are tools, not authorities: tool output is data; a person approves every merge; protected paths are not edited by agents (ADR-084, ADR-086) | ADR: ADR-084, ADR-086; `docs/architecture/protected-paths.md` |

### Sign-in and sessions

| ID | Boundary | Threat | Mitigation | Coverage |
|---|---|---|---|---|
| AU-01 | TB2 | A staff session is established without a second factor | The BFF refuses any provider token without an MFA assertion, whatever the provider is set to; no password method exists (DEC-22, ADR-165) | Tested: `backend/tests/integration/test_staff_session.py` |
| AU-02 | TB2 | A stolen refresh cookie is replayed | Refresh tokens are sealed server-side; the cookie is `__Host-`, HttpOnly, Secure, SameSite strict; a reused cookie ends the session | Tested: `backend/tests/integration/test_staff_session.py` |
| AU-03 | TB2 | A fresh-MFA action (exports, holds, TIN reveal, retention) runs on a stale sign-in | The matrix marks them `mfa_recent: required`; the list in `docs/architecture/fresh-mfa-actions.yaml` is held to the matrix | Tested: `backend/tests/unit/quality/test_fresh_mfa_actions.py` |
| AU-04 | TB2 | Tokens sit in browser storage where injected script can read them | The SPA holds the access token in memory only; no in-browser code exchange; `connect-src 'self'` | Tested: `apps/web/src/app-core/auth/session.test.ts`. ADR: ADR-165 |
| AU-05 | TB2 | A portal email is enumerated, or a code brute-forced | Every email gets the same answer; three wrong codes lock the email on that host for 15 minutes; parallel challenges share the count; codes expire | Tested: `backend/tests/integration/test_portal_sign_in.py` |
| AU-06 | TB2 | A portal token is used on another firm's portal or on the firm app | Portal sessions are opaque, checked on every request and pinned to the tenant and host they were minted on; elsewhere they are no session (ADR-168) | Tested: `backend/tests/integration/test_portal_sign_in.py` |
| AU-07 | TB2 | An owner or signer finishes portal sign-in without a second factor | The MFA floor for owner, signing and approving designations fails closed (a slow or missing predicate means MFA is required); a firm may widen and never narrow it; backup codes verify once (DEC-34) | Tested: `backend/tests/integration/test_portal_mfa.py` |
| AU-08 | TB2 | A client keeps access after a grant is revoked | Revocation ends the person's portal sessions and trusted devices; a revoked grant ends what the token reaches | Tested: `backend/tests/integration/test_portal_sign_in.py`, `backend/tests/integration/test_portal_mfa.py` (`test_ac11_access_changed_ends_sessions_and_revokes_trusted_devices`) |
| AU-09 | TB2 | A staff access token is used after sign-out, a detected cookie reuse or the session's limits | Sign-out, reuse and the limits end the refresh session (ADR-165). API requests verify the provider's JWT alone, which lives up to 3600 s (`identity/tokens.py`), so an issued token keeps working until it expires. Provider session revoke is Q-01-T17 | Partial: `backend/tests/integration/test_staff_session.py` (the session side). Gap: no check of session liveness per request (see Gaps; ASVS G-02) |
| AU-10 | TB2 | A portal backup code is guessed, or recovered from a leaked digest | Eight codes, single use, with the second-step lockout (3 tries, 15 minutes, across firms). Each code carries 80 bits and is stored as an unsalted SHA-256 | Tested: `backend/tests/integration/test_portal_mfa.py` (`test_ac11_a_backup_code_verifies_once`, `test_ac11_second_step_guesses_are_the_persons_across_firms`). Gap: below ASVS's 112 bits, no salt (see Gaps; ASVS G-05) |

### Portal hosts and reads

| ID | Boundary | Threat | Mitigation | Coverage |
|---|---|---|---|---|
| PO-01 | TB2 | The request host is trusted for authorisation, so a crafted host reaches another firm | The host picks branding only; authorisation comes from the session's membership and grants (ADR-163 §5); unknown or malformed hosts get the same neutral shape | Tested: `backend/tests/integration/test_portal_branding.py`, `backend/tests/integration/test_portal_sign_in.py` |
| PO-02 | TB2 | Branding leaks firm data or serves active content | Branding carries Public fields only and no tenant id; the logo is re-encoded server-side and served same-origin | Tested: `backend/tests/integration/test_portal_branding.py`. Not built: firm-owned custom domains and their certificates (P-11, RB-21); add rows when they ship |
| PO-03 | TB2 | The role union over-grants: a taxpayer or third party sees what only an owner may | Grants are scoped to a client, an entity or an engagement; landing and reads follow the union of the person's grants; client roles only respond (ADR-146) | Tested: `backend/tests/integration/test_portal_sign_in.py` (landing follows the role union), `backend/tests/integration/test_portal_home.py`. The POR-03/04 section is a stub until R-01 makes it live |

### Invitations (v2)

| ID | Boundary | Threat | Mitigation | Coverage |
|---|---|---|---|---|
| IN-01 | TB2 | The invitation preview is an oracle: it tells a stranger whether a token, an address or a firm exists | Every failure (expired, used, revoked, malformed, another host's, a staff member's address) answers the same 404. Misses are counted per viewer address, and after the limit nothing is found; misses never block a valid token for a viewer with no trusted address | Tested: `backend/tests/integration/test_portal_invitations.py` (`test_ac12_every_failure_answers_the_same_404`, `test_ac12_misses_are_counted_per_address_and_then_nothing_is_found`, `test_preview_misses_lock_only_the_viewer_that_made_them`) |
| IN-02 | TB2 | A pending invitee's session reaches data before they accept | A right code mints a session pinned to tenant and host that authorises nothing until acceptance creates the membership and grants; start sends the invitee a code and nothing else | Tested: `test_the_invitees_session_authorises_nothing_before_acceptance`, `test_start_with_the_invitation_token_sends_the_invitee_a_code_and_nothing_else` |
| IN-03 | TB2 | An invitation over-grants, or outlives the inviter's authority | Template grants are limited to the inviting engagement and to 1–200 scope ids; acceptance re-checks the inviter's authority in one unit of work; offboarding, a role change or leaving the engagement revokes the person's pending invitations; a contact of another client is refused | Tested: `test_create_invitation_v2_stores_a_template_within_the_engagement_only`, `test_inv5_acceptance_rechecks_the_inviters_authority`, `test_inv5_offboarding_or_a_role_change_revokes_the_persons_pending_invitations`, `test_create_invitation_refuses_a_contact_of_another_client`, `test_ac13_one_unit_of_work_a_failure_after_the_grants_rolls_them_back` |
| IN-04 | TB2 | A link is reused or replayed, or an owner skips the second step by accepting | Links are single use for 14 days (DEC-35); a reused token, wrong terms version or expired invitation gets the same 404; acceptance ends the invitee's other sessions in the firm; an owner template meets the MFA floor inside the acceptance and on every request after | Tested: `test_ac13_a_reused_token_wrong_terms_or_expired_invitation_gets_the_same_404`, `test_acceptance_ends_the_invitees_other_sessions_in_the_firm`, `test_an_owner_template_asks_for_the_second_step_after_acceptance`, `test_the_floor_is_met_inside_the_acceptance_and_enforced_on_every_request` |

### Independence (G2 v2)

| ID | Boundary | Threat | Mitigation | Coverage |
|---|---|---|---|---|
| G2-01 | TB2, TB6 | A person who has not confirmed independence is assigned, signs off, grants client access or messages the client on an attest engagement, directly or through the agent | Authorisation layer 3b denies every non-read marked action when the person is not cleared and the client is an attest client. An unknown or unregistered attest flag counts as attest (fail closed). Agents inherit the initiator's refusal; walls are checked first; assignment is a partner's or manager's action (ADR-164) | Tested: `backend/tests/integration/test_g2_v2.py` (`test_ac13_ana_opens_the_attest_engagement_but_cannot_be_assigned_or_sign_off`, `test_ac16_once_ana_confirms_she_is_cleared_assigned_and_signs`, `test_ac13_assignment_is_the_partners_or_managers_never_the_staff_members`), `backend/tests/unit/identity/test_independence.py` (the closed list, agents, support, walls before independence) |
| G2-02 | TB2 | A firm setting loosens the gate | `g2_blocks_view` can only tighten (it restores the read gate on attest engagements). A matrix cell may never name it, so it can never grant; non-attest work is not gated | Tested: `test_ac15_g2_blocks_view_restores_the_read_gate_on_attest_engagements`, `test_ac14_a_non_attest_close_is_not_gated`; `backend/tests/unit/identity/test_independence.py` (the setting cannot be named by a cell) |

### Evidence, citations and the viewer

| ID | Boundary | Threat | Mitigation | Coverage |
|---|---|---|---|---|
| EV-01 | TB1 | An oversized or disallowed file in a portal drop reaches the parser | The drop contract refuses by size (413) and type (415) before storage; scanning comes before parsing (ADR-110); the drop will apply the same upload policy as firm uploads (EV-06) | Stub: `backend/tests/contracts/c5_portal_pbc/test_c5_portal_pbc_stub.py` declares the responses; the live route lands with R-01 and needs its own test |
| EV-02 | TB5 | A citation names a page or region it does not quote, or a kind with no verifier is shown as verified | Each citation is verified by a registered verifier against the stored layer; an unregistered kind is written `locator_invalid` and never shown as verified (P-03-T06) | Tested: `backend/tests/integration/trust_kit/test_citation_verifiers.py`, `backend/tests/unit/evidence/test_citation_matching.py`, `backend/tests/unit/agents/test_agent_citations.py` |
| EV-03 | TB7 | The viewer renders the raw client file in the browser | Previews are server-made page images; the raw file is never rendered (SPEC-029 AC-12, ADR-110); the manifest carries geometry and mask tokens, never text | Tested: `backend/tests/integration/trust_kit/test_viewer.py` (`test_ac16_the_manifest_is_geometry_and_tokens_and_processing_until_masked`), `backend/tests/contracts/c04_citations_viewer/test_c4_contract.py` |
| EV-04 | TB7 | The viewer serves a page with personal data unmasked, or to someone walled or a client | Only a masked rendition is served; none exists until masking lands, so every page is 409 `preview_outdated` (DEC-266). A page with no PII scan reads `not_scannable` (fail closed). A walled version is 404 and a client principal 403 (INV-4). A served page is `no-store`, `nosniff` and `default-src 'none'`, and only after its access event is written | Tested: `test_viewer.py` (`test_ac24_no_unmasked_page_is_ever_served`, `test_ac24_a_masked_page_is_served_after_its_read_is_logged`, `test_ac22_walls_answer_404_and_clients_403`). The legacy upload and inbox page routes still serve unmasked previews until P-03-T15 switches them (DEC-266) |
| EV-05 | TB7, TB8 | Viewer search leaks words or the query | Search answers rectangles only, never text; skips masked words and pages no scan covers; the query is never logged or stored; at least three characters; at most 200 hits | Tested: `test_viewer.py` (`test_ac21_search_answers_rects_only_never_logs_the_query_and_skips_masks`, `test_search_fails_closed_on_pages_no_pii_scan_covers`, `test_search_leaves_an_access_event_and_never_the_query`, `test_search_needs_three_characters_and_caps_its_pages`) |
| EV-06 | TB1 | A hostile or active file is stored as an allowed type, then extracted or previewed | **Intended control (client upload policy, decided 2026-10-24; being built in another workstream):** a 50 MB limit; type decided by content sniffing against an allowlist, with a matching extension; HTML, SVG, JavaScript and macro-enabled Office files refused; a PDF with active content is stored but never extracted or previewed, and is flagged. **Today:** any text is kept as CSV, and macro and legacy Office files, HTML, SVG and JavaScript are stored; PDFs with JavaScript are extracted and previewed; the limit is 25 MB (ED-018 to ED-021) | Held as strict xfails in `backend/tests/security/test_upload_hostile_files.py` (`test_dec58_a_30_mb_pdf_is_within_the_limit`, `test_dec58_a_type_outside_the_seven_is_refused`, `test_q03_a_pdf_with_javascript_is_quarantined_not_previewed`, `test_dec58_heic_is_kept_as_is_with_no_preview_yet`). Moves to Tested when they pass. Downloads stay `attachment` with `nosniff`, and previews stay server-made PNGs |

### Compliance records

| ID | Boundary | Threat | Mitigation | Coverage |
|---|---|---|---|---|
| CR-01 | TB2 | A legal hold is placed, lifted or bypassed by someone without the right, or evidence under a hold is erased | Fresh MFA and a person to place or lift; the table binds the person; the hold check fails closed when unregistered; holds are reference-counted per object (ADR-033) | Tested: `backend/tests/integration/test_legal_holds.py`, `backend/tests/unit/kernel/test_holds.py` |
| CR-02 | TB2 | An incident is recorded by an agent or the wrong role, or an Accrued incident entry is forged by a firm user | `incident.manage` is the security admin's only; the table is insert-only and binds a firm entry to the session's person and an Accrued entry to the system; the register is behind `compliance.incidents` | Tested: `backend/tests/integration/test_security_incidents.py` (`test_ac38_only_the_qi_records_and_the_register_is_behind_its_flag`, `test_ac38_the_database_binds_a_firm_entry_to_its_person_and_is_insert_only`, `test_ac39_only_the_system_writes_an_accrued_entry`) |
| CR-05 | TB2, TB7 | Staff propagation writes into the wrong firm, repeats with changed facts, or is forged from a firm session | Propagation is a staff-issuer route and CLI (`make incident-propagate`) with a reason; it reaches only firms with the register on; it is idempotent on Accrued's reference, and a repeat with changed facts is refused and writes nothing; a firm session cannot forge the staff record; one firm's failure does not stop the rest | Tested: `test_security_incidents.py` (`test_ac39_staff_start_only_for_firms_with_the_register_on`, `test_review_a_repeat_with_changed_facts_is_refused_and_writes_nothing`, `test_review_a_firm_session_cannot_forge_the_staff_record`, `test_review_a_firm_that_keeps_failing_does_not_stop_the_firms_after_it`), `backend/tests/workflows/test_incident_propagation_replay.py` |
| CR-03 | TB8 | A whole-firm export is taken by one person or its link is shared | Not built. Planned: two distinct people, fresh MFA, a short-lived link inside a 7-day window, a SHA-256 manifest (Q-02-T43, Q-02-T46) | Planned: Q-02-T43 |
| CR-04 | TB7, TB8 | A run trace export carries more than the trace, or is taken by the agent | Export is a person's action with fresh MFA (`run_trace.export`, agent denied); canonical JSON with a manifest; model text is Confidential and shown only through the sanitising component | Tested: `backend/tests/security/test_permission_matrix_generated.py` (agent denied). ADR: ADR-065. Gap: no integration test of the export body (see Gaps) |

### Outbound messages

| ID | Boundary | Threat | Mitigation | Coverage |
|---|---|---|---|---|
| OB-01 | TB7 | The agent sends a follow-up to a client | A follow-up is drafted from a published template and sent only by a person, after the Undo window; `follow_up.sent` is in the human-only register | Tested: `backend/tests/integration/test_follow_ups_v2.py`, `backend/tests/integration/test_human_only_guard.py` |
| OB-02 | TB7 | Notification email carries identifiers or client content, or cannot be stopped | Email text is a published template (content, not code); the transport runs the mechanical body check on every message (SSNs, TINs, account numbers and tax amounts refused, `communications/transport.py`); `notifications.email` is a per-firm kill switch re-checked before each send (RB-31) | Tested: `backend/tests/acceptance/test_q01_ses_transport.py` (the body check on the transport), `backend/tests/workflows/test_notification_email_replay.py`. Gap: no test sends a notification email through it end to end (see Gaps) |

## Cross-tenant and TRI exposure: the short version

A hostile string cannot read another firm's data because it never carries authority: it arrives as data inside a block, the model's reply is schema-checked, and anything the reply asks for goes through the same `authorise` and row-level-security path a person would. The remaining exposure is therefore (1) a query that skips the tenant session (CT-01, closed by the generated isolation test), (2) state shared across firms by design: caches, examples, embeddings (CT-03, CT-04, the least-tested rows), and (3) the model route and its terms (CT-07, DB-01 to DB-03). Tax return information and personal identifiers add a content-level risk that tenancy cannot address. The control is to refuse or mask them before they reach a model (TRI-01). The gateway refusal of unmasked TINs is built (Q-02-T32, ADR-167); the consent gate (ADR-167 §3, T-01) is not. Until it exists, no tax data goes to a model.

## Gaps found while writing this model

Each gap is a row above whose evidence is an ADR only. None is a new decision; each needs a test or a task. The builder decides whether to open a task.

| Gap | Rows | Suggested closure |
|---|---|---|
| The server-side output sanitiser (`backend/src/abacus/ai_gateway/sanitise.py`) has no backend test | HC-10 | A unit test for each link form it strips and the allowlist case (SPEC-006 AC-1, AC-2) |
| No test names the outbound scope checker | TL-07 | A test with seeded out-of-scope values, written when the first model-drafted message is allowed |
| No test shows caches, examples and result reuse are firm-scoped | CT-03, CT-04 | A two-firm gateway test: identical input, separate runs, no shared example |
| No test names the global-profile rejection | DB-02 | A settings-validation test, in Q-02-T11 |
| Event-stream payloads (identifiers only) have no test because the channel is not built | CT-09 | A test when the real-time channel ships; pen test #2 |
| Learning-loop safeguards have no test | TL-09 | A test that a correction is retrievable immediately and cannot become a firm rule without approval |
| ADR-168 names `test_portal_host_pinning.py`; host pinning is tested inside `test_portal_sign_in.py` instead | AU-06, PO-01 | Keep the cases where they are, or split them into the named file; either way the ADR's checklist item is met |
| The run trace export has no integration test of its body | CR-04 | A test that the export holds only the trace's rows and the manifest matches the bytes |
| No test sends a notification email through the body check end to end | OB-02 | A test that a `notification.<kind>` template rendering a TIN-shaped value settles `failed` and nothing reaches the sink |
| The portal drop is a stub; pen test #1 meets it only if R-01 makes it live by the build pin. The C4 viewer is live behind its flag but serves no page until masking (P-03-T13, T15) | EV-01, EV-04 | R-01 adds its tests before the pin, or the scope letter marks it out; the legacy preview routes stay unmasked until P-03-T15 (DEC-266) |
| The upload policy decided 2026-10-24 is not yet on `main` | EV-06 | The workstream building it turns ED-018 to ED-021's strict xfails into passes before the pin (Q-03-T016) |
| A staff access token outlives sign-out and the session limits by up to its lifetime | AU-09 | Q-01-T17's provider revoke plus a per-request session check or a shorter token, or the scope letter states the lifetime (ASVS G-02) |
| Portal backup codes are 80 bits with an unsalted digest | AU-10 | 128-bit codes, or a per-code salt (ASVS G-05) |
| The named pen-scope files `test_portal_scope_isolation.py` and `test_portal_host_pinning.py` do not exist | IN-, PO-, AU-06 | P-08-T25 by Fri Feb 12, 2027 |

## Review

| Date | Reviewer | Scope | Result |
|---|---|---|---|
| 2026-10-24 | Q-03-T018 second pass after the S7 batch (TASK-1178; self-review; N's review is still open) | TRI-01, TRI-03 and TRI-04 moved to Tested (ADR-167); new rows AU-09, AU-10, IN-01 to IN-04, G2-01, G2-02, EV-04 to EV-06, CR-05; EV-01, EV-03, CR-02 and AU-08 revised; scope table rows for invitations v2, G2 v2, the TIN refusal and the live viewer; the upload policy recorded as the intended control. Every new test path was opened, and each named test was found | Five gaps added; one closed (the viewer is no longer a stub) |
| 2026-10-24 | Q-03-T018 refresh (self-review; N's review is the row's acceptance and is still open) | The pen test #1 scope table; new rows AU-01 to AU-08, PO-01 to PO-03, EV-01 to EV-03, CR-01 to CR-04, OB-01, OB-02; coverage of TL-01, TL-08, CT-01, CT-08 and TRI-05 moved to the tests on `main`; every cited test path checked to exist | Four gaps added. Not built and named as such: firm export, custom domains, the live portal drop and viewer |
| 2026-10-20 | Authoring session (self-review). The security reviewer subagent (`.claude/agents/security-reviewer.md`) has not been run; it is optional under the solo amendment and blocks nothing | Walked the reviewer's checklist items 5 to 12, 17 and 19 against this file; checked that every cited test path exists and every cited task id is in `docs/plan/epics/Q-02.tasks.csv`; checked that no row names a firm, a person, an amount or a secret | No threat row lacks a coverage entry. Six gaps listed above. Rows TRI-01 to TRI-05 are plan-only until Q-02-T25 and Q-02-T32 land |

## Update checklist (copy into the pull request that adds an agent, tool or data source)

- [ ] Which strings from clients or client systems does it read? Each is named as untrusted in the agent spec.
- [ ] Which tools does it call? Each is narrow and typed, and authorises against the agent context.
- [ ] Which decision actions does it come near? None are in its context.
- [ ] Which routes may it use? The data-boundary conditions in ADR-115 are unchanged, or an ADR says why.
- [ ] Does it touch tax return information, identifiers or health-plan data? The flags and the gateway refusal apply.
- [ ] What does it write back, and where is that shown? Plain text only, hidden in shadow.
- [ ] Which rows above change, and which test or evaluation case covers the new path?
