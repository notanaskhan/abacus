# Architecture Decision Records

All accepted ADRs are binding. See `_TEMPLATE.md` to propose a new one.

| ID | Decision | Risk zone | Status |
|---|---|---|---|
| [ADR-001](ADR-001-client-records-owned-by-firm.md) | Client records are owned by each firm | red | accepted |
| [ADR-002](ADR-002-global-identity-per-firm-membership.md) | Global user identity with per-firm memberships | red | accepted |
| [ADR-003](ADR-003-requests-evidence-many-to-many.md) | Requests and evidence are linked many-to-many through fulfilments | amber | accepted |
| [ADR-004](ADR-004-evidence-ledger-immutable-versioned.md) | Evidence and ledger data are versioned and immutable | red | accepted |
| [ADR-005](ADR-005-agents-propose-humans-decide.md) | Agents propose; humans decide | red | accepted |
| [ADR-006](ADR-006-model-client-entities.md) | Model client entities from day one | amber | accepted |
| [ADR-007](ADR-007-append-only-audit-trail.md) | Append-only audit trail in a separate event log | red | accepted |
| [ADR-008](ADR-008-modular-monolith.md) | Modular monolith | amber | accepted |
| [ADR-009](ADR-009-languages.md) | Python for the backend, TypeScript for the frontend, strict typing in both | amber | accepted |
| [ADR-010](ADR-010-monorepo.md) | Monorepo with enforced boundaries and one command surface | amber | superseded by ADR-101 |
| [ADR-011](ADR-011-react-spa.md) | React single-page app built with Vite | amber | accepted |
| [ADR-012](ADR-012-fastapi.md) | FastAPI backend with enforced layering | amber | accepted |
| [ADR-013](ADR-013-rest-openapi-pydantic.md) | REST and OpenAPI, with Pydantic as the schema source of truth | amber | accepted |
| [ADR-014](ADR-014-postgres-shared-schema-rls.md) | PostgreSQL with shared schema and row-level security | red | accepted |
| [ADR-015](ADR-015-sqlalchemy-alembic.md) | SQLAlchemy 2.0 and Alembic, with safe migrations | amber | accepted |
| [ADR-016](ADR-016-s3-object-lock.md) | Evidence files in S3 with Object Lock | red | accepted |
| [ADR-017](ADR-017-temporal.md) | Temporal for durable workflows | amber | accepted |
| [ADR-018](ADR-018-transactional-outbox.md) | Transactional outbox and unit of work | red | accepted |
| [ADR-019](ADR-019-ai-gateway.md) | Thin internal AI gateway | red | accepted |
| [ADR-020](ADR-020-authn-bought-authz-inhouse.md) | Bought authentication, in-house authorisation | red | accepted |
| [ADR-021](ADR-021-aws-terraform.md) | AWS in a US region, defined in Terraform | amber | accepted |
| [ADR-022](ADR-022-observability.md) | OpenTelemetry, Sentry and self-hosted LLM tracing | amber | accepted |
| [ADR-023](ADR-023-layered-authorisation-model.md) | Four-layer authorisation model | red | accepted |
| [ADR-024](ADR-024-need-to-know-metadata-vs-content.md) | Need to know: admins see engagement metadata, not content | red | accepted |
| [ADR-025](ADR-025-agent-permissions-intersection.md) | Agent permissions are an intersection, enforced in tools | red | accepted |
| [ADR-026](ADR-026-ethical-walls.md) | Ethical walls override every role | red | accepted |
| [ADR-027](ADR-027-inhouse-policy-as-code.md) | In-house policy-as-code with a protected permission matrix | red | accepted |
| [ADR-028](ADR-028-no-standing-staff-access.md) | No standing platform-staff access; audited break-glass | red | accepted |
| [ADR-029](ADR-029-identity-vendor.md) | B2B identity vendor for authentication only | red | accepted |
| [ADR-030](ADR-030-authentication-policy.md) | Authentication and session policy | red | accepted |
| [ADR-031](ADR-031-data-classification.md) | Four-level data classification tagged on every field | red | accepted |
| [ADR-032](ADR-032-retention.md) | Firm-configurable retention with enforced minimums | red | accepted |
| [ADR-033](ADR-033-legal-hold.md) | Legal hold on engagements and clients | red | accepted |
| [ADR-034](ADR-034-deletion-offboarding.md) | No deletion inside engagements; offboarding by export and crypto-shredding | red | accepted |
| [ADR-035](ADR-035-per-tenant-keys.md) | Per-tenant encryption keys for restricted data | red | accepted |
| [ADR-036](ADR-036-engagement-export.md) | Engagement export in an open format | amber | accepted |
| [ADR-037](ADR-037-connector-contract.md) | One connector contract with capability declarations | amber | accepted |
| [ADR-038](ADR-038-connector-pipeline.md) | Six-stage pipeline with immutable raw payloads and control totals | red | accepted |
| [ADR-039](ADR-039-ledger-model-provenance.md) | Common ledger model with source identifiers and authorship | amber | accepted |
| [ADR-040](ADR-040-platform-enforced-read-only.md) | Read-only access enforced by the platform | red | accepted |
| [ADR-041](ADR-041-sync-and-change-detection.md) | Sync modes and layered change detection | amber | accepted |
| [ADR-042](ADR-042-deterministic-rendering.md) | Deterministic evidence rendering | amber | accepted |
| [ADR-043](ADR-043-rate-limits-fairness.md) | Rate limiting, fair queuing and resilient pulls | amber | accepted |
| [ADR-044](ADR-044-connector-testing.md) | Connector testing strategy | amber | accepted |
| [ADR-045](ADR-045-ledger-prioritisation.md) | First ledger chosen from data; direct connectors plus a unified API | amber | accepted |
| [ADR-046](ADR-046-agency-at-coordination.md) | Agency at the coordination level, reliability at the step level | amber | accepted |
| [ADR-047](ADR-047-declared-agent-specs.md) | Every agent is declared in a specification | amber | accepted |
| [ADR-048](ADR-048-agent-loop-harness.md) | Agent loop harness on Temporal | amber | accepted |
| [ADR-049](ADR-049-narrow-typed-tools.md) | Narrow, typed, intent-named tools | red | accepted |
| [ADR-050](ADR-050-code-computes-models-judge.md) | Code computes, models judge | red | accepted |
| [ADR-051](ADR-051-context-builders.md) | Context assembled by code in five cache-friendly layers | amber | accepted |
| [ADR-052](ADR-052-hostile-client-content.md) | Client content is treated as hostile | red | accepted |
| [ADR-053](ADR-053-structured-scoped-memory.md) | Structured, attributed and scoped memory | red | accepted |
| [ADR-054](ADR-054-handoff-contract.md) | Standard human handoff contract | amber | accepted |
| [ADR-055](ADR-055-model-tiering-cost.md) | Model tiers, cascades, caching, batching and reuse | amber | accepted |
| [ADR-056](ADR-056-standards-licensing.md) | No licensed standards text without a licence | amber | accepted |
| [ADR-057](ADR-057-no-orchestration-framework.md) | Temporal is the only orchestrator; no agent framework for now | amber | accepted |
| [ADR-058](ADR-058-agent-hierarchy.md) | Agent hierarchy: engagement agents and specialists | amber | accepted |
| [ADR-059](ADR-059-coordination-via-state.md) | Agents coordinate through shared state and events | red | accepted |
| [ADR-060](ADR-060-hybrid-decisions.md) | Hybrid decision-making for the engagement agent | amber | accepted |
| [ADR-061](ADR-061-autonomy-levels.md) | Four autonomy levels; decisions remain human | red | accepted |
| [ADR-062](ADR-062-long-running-agents-temporal.md) | Engagement agents as long-lived Temporal workflows | amber | accepted |
| [ADR-063](ADR-063-visible-agency.md) | Agency is visible | amber | accepted |
| [ADR-064](ADR-064-ai-threat-model.md) | Living AI threat model; all client-system strings are untrusted | red | accepted |
| [ADR-065](ADR-065-output-controls.md) | Output controls on agent-generated content | red | accepted |
| [ADR-066](ADR-066-citation-verification.md) | Citations are verified by code | red | accepted |
| [ADR-067](ADR-067-tenant-scoped-caches.md) | Caches and examples never cross firms | red | accepted |
| [ADR-068](ADR-068-learning-loop-safeguards.md) | Learning-loop safeguards | amber | accepted |
| [ADR-069](ADR-069-budget-hierarchy.md) | Budget hierarchy and denial-of-wallet controls | red | accepted |
| [ADR-070](ADR-070-cost-attribution-regression.md) | Cost attribution, cost regression gates and a cost ceiling | amber | accepted |
| [ADR-071](ADR-071-work-classes-fairness.md) | Work classes and fair concurrency | amber | accepted |
| [ADR-072](ADR-072-admission-control-degradation.md) | Admission control and graceful degradation | amber | accepted |
| [ADR-073](ADR-073-two-routes-same-model.md) | Two access routes to the same model family | amber | accepted |
| [ADR-074](ADR-074-model-prompt-lifecycle.md) | Pinned models and prompts with gated upgrades | amber | accepted |
| [ADR-075](ADR-075-busy-season-readiness.md) | Busy-season readiness | amber | accepted |
| [ADR-076](ADR-076-tests-vs-evals.md) | Tests are deterministic; evaluations call real models | amber | accepted |
| [ADR-077](ADR-077-test-layers-tooling.md) | Test layers and tooling | amber | accepted |
| [ADR-078](ADR-078-separate-test-author.md) | Separate test author for amber and red work | amber | accepted |
| [ADR-079](ADR-079-coverage-mutation.md) | Coverage floors, mutation testing and test hygiene | amber | accepted |
| [ADR-080](ADR-080-security-test-suite.md) | Security tests on every pull request | red | accepted |
| [ADR-081](ADR-081-evaluation-suites.md) | Per-agent evaluation suites and grading | amber | accepted |
| [ADR-082](ADR-082-evaluation-cadence-drift.md) | Evaluation cadence and production drift monitoring | amber | accepted |
| [ADR-083](ADR-083-ci-pipeline.md) | Five-stage CI pipeline and banned-pattern lints | amber | accepted |
| [ADR-084](ADR-084-reviewer-agents.md) | Reviewer agents in CI | amber | accepted |
| [ADR-085](ADR-085-synthetic-test-data.md) | Synthetic test data; no real client data in the repository | red | accepted |
| [ADR-086](ADR-086-earned-autonomy.md) | Earned autonomy for coding agents | amber | accepted |
| [ADR-087](ADR-087-environments.md) | Separated environments; production data stays in production | red | accepted |
| [ADR-088](ADR-088-build-once-promote.md) | Build once, promote; health-checked rollouts | amber | accepted |
| [ADR-089](ADR-089-feature-flags.md) | Release decoupled from deploy through feature flags | amber | accepted |
| [ADR-090](ADR-090-workflow-safe-deploys.md) | Workflow-safe deployments | red | accepted |
| [ADR-091](ADR-091-production-migrations.md) | Safe production migrations | red | accepted |
| [ADR-092](ADR-092-busy-season-change-policy.md) | Reduced-risk change policy from January to March | amber | accepted |
| [ADR-093](ADR-093-slos-error-budgets.md) | Reliability targets, error budgets and paging policy | amber | accepted |
| [ADR-094](ADR-094-observability-practice.md) | Observability in practice | amber | accepted |
| [ADR-095](ADR-095-postgres-truth.md) | Postgres holds the truth; agents are rebuildable | red | accepted |
| [ADR-096](ADR-096-backups-dr.md) | Backups, disaster recovery and integrity verification | red | accepted |
| [ADR-097](ADR-097-incident-response.md) | Incident response and kill switches | red | accepted |
| [ADR-098](ADR-098-runbooks.md) | Rehearsed runbooks for foreseeable scenarios | amber | accepted |
| [ADR-099](ADR-099-security-operations.md) | Security operations baseline | red | accepted |
| [ADR-100](ADR-100-founder-spof.md) | Mitigating founder single point of failure | amber | accepted |
| [ADR-101](ADR-101-namespaced-backend-layout.md) | Namespaced backend package layout | amber | accepted |
| [ADR-102](ADR-102-visible-takes-action-and-engagement-column.md) | visible() takes the read action and the engagement column | red | accepted |
| [ADR-103](ADR-103-table-ownership-registry.md) | Table ownership by registry, not name prefix | amber | accepted |
| [ADR-104](ADR-104-client-side-envelope-encryption.md) | Client-side envelope encryption under per-tenant keys | red | accepted |
| [ADR-105](ADR-105-essential-flag-name.md) | An agent's essential or deferrable flag is named `essential` (amends ADR-069's guidance) | amber | accepted |
| [ADR-106](ADR-106-module-registrations.md) | Modules hand facts to each other by registration, and evidence may depend on requests | amber | accepted |
| [ADR-107](ADR-107-ledger-file-import.md) | A file-based ledger import is a connector with reduced capabilities | red | accepted |
| [ADR-108](ADR-108-client-access-ladder.md) | Clients choose to connect or to export; connecting is never required | amber | accepted |
| [ADR-109](ADR-109-comments.md) | Comments are append-only, pinned to a version, and internal unless shared | red | accepted |
| [ADR-110](ADR-110-upload-processing.md) | Uploads are scanned, then parsed in isolation; extraction never alters evidence | red | accepted |
| [ADR-111](ADR-111-client-prechecks.md) | Client-facing pre-checks are mechanical, with fixed wording | amber | accepted |
| [ADR-112](ADR-112-data-boundary.md) | AI runs only on synthetic tenants, enforced in the AI gateway | red | superseded by ADR-115 |
| [ADR-113](ADR-113-client-data-route.md) | Client data uses Bedrock in-region only; the direct API is for synthetic data | red | accepted |
| [ADR-114](ADR-114-provider-terms.md) | A model route carries client data only with recorded, current provider terms | red | accepted |
| [ADR-115](ADR-115-data-boundary-real-firms.md) | AI sees a real firm's data only through SPEC-036's five conditions, enforced in the gateway | red | accepted |
| [ADR-131](ADR-131-workpapers.md) | A workpaper is rendered by code, versioned, and signed off by people; it never changes once reviewed | red | accepted |
| [ADR-132](ADR-132-procedures.md) | In a procedure, code builds the population and selects the sample; agents assess items; people conclude | red | accepted |
| [ADR-133](ADR-133-product-naming.md) | The product is "Accrued" in every UI string and document; abacus is the code namespace only | amber | accepted |
| [ADR-134](ADR-134-fieldwork-on-review-grammar.md) | Fieldwork sign-off, review notes and workpapers ride the review grammar (proposal P-07, epic P-04) | red | accepted |
| [ADR-135](ADR-135-pre-launch-migration-policy.md) | Until the first real firm is live, a breaking change is one reversible migration | red | accepted |
| [ADR-136](ADR-136-engagement-work-items-gates.md) | Engagements hold work items, and the server enforces the gates | red | accepted |
| [ADR-137](ADR-137-module-map-29.md) | The backend has 29 modules with a one-way dependency graph | amber | accepted |
| [ADR-138](ADR-138-status-registry.md) | One status vocabulary file is the contract; enums, OpenAPI and UI tables are generated from it | amber | accepted |
| [ADR-139](ADR-139-api-conventions.md) | API conventions - list envelope, allowed_actions, error catalogue, idempotency, classification, versioning | amber | accepted |
| [ADR-140](ADR-140-per-module-registries.md) | Registries and the permission matrix are split per module | amber | accepted |
| [ADR-141](ADR-141-authentication-workos.md) | Authentication and sessions use WorkOS AuthKit, with a BFF session for the portal | red | accepted |
| [ADR-142](ADR-142-aws-topology-regions.md) | AWS production topology - us-east-2 primary, us-west-2 DR | red | accepted |
| [ADR-143](ADR-143-clock-scenario-synthetic-marker.md) | Business clock, scenario loader and the firm-level synthetic marker | amber | accepted |
| [ADR-144](ADR-144-request-status-enum-migration.md) | Request status enum migration, follow-up rename and the wrong_document reason | red | accepted |
| [ADR-145](ADR-145-generalised-visible-scope-kinds.md) | Generalised visible() with declared scope kinds | red | accepted |
| [ADR-146](ADR-146-client-identity-scoped-grants-portal-mfa.md) | Client identity - scoped grants, link principals and portal MFA | red | accepted |
| [ADR-147](ADR-147-role-catalogue-need-to-know.md) | Role catalogue and need-to-know - two axes plus work-item functions | red | accepted |
| [ADR-148](ADR-148-entitlements-agent-minutes-budgets.md) | Entitlements, agent-minutes and two-layer budgets | amber | accepted |
| [ADR-149](ADR-149-e-signature-record-mode-then-docusign.md) | E-signature - record mode first, then DocuSign embedded with ID Verification behind an EnvelopeProvider port | red | proposed |
| [ADR-150](ADR-150-integrations-module-write-capabilities.md) | Integrations module and the declared write-capability framework | red | proposed |
| [ADR-151](ADR-151-busy-season-change-policy-from-go-live.md) | Busy-season change policy - the freeze starts at the first real go-live | red | proposed |
| [ADR-152](ADR-152-unauthenticated-operational-routes.md) | Unauthenticated operational routes - /healthz and portal branding on an explicit allowlist | red | proposed |
| [ADR-153](ADR-153-malware-scanning-service.md) | Malware scanning service - ClamAV clamd, synchronous, fail closed | red | proposed |
| [ADR-154](ADR-154-observability-on-call-vendors.md) | Observability and on-call vendors - CloudWatch, X-Ray, Sentry and Better Stack | red | proposed |
| [ADR-155](ADR-155-design-system.md) | packages/ui is the Accrued design system - Tailwind v4 tokens, self-hosted fonts, Radix for behaviour, the AA ink ladder | amber | accepted |
| [ADR-156](ADR-156-tenant-key-provisioning.md) | Tenant key provisioning - one multi-Region key per firm, created by a keyops worker | red | proposed |
| [ADR-157](ADR-157-platform-controls-kill-switches.md) | Platform controls and kill switches - database rows read through one function, changed only by operators | red | proposed |
| [ADR-158](ADR-158-client-scoped-files-cross-engagement-fulfilment.md) | Client-scoped files and cross-engagement fulfilment - evidence with a client and no engagement; reuse by reference, same client only | red | proposed |
| [ADR-159](ADR-159-archive-seal-immutability-hash-chain-object-lock.md) | Archive seal, database immutability, the audit hash chain and Object Lock modes | red | proposed |
| [ADR-160](ADR-160-review-grammar.md) | Review grammar - sign-offs, review notes, issues, decision cards, checkpoints and field history in one red review module | red | accepted |
| [ADR-161](ADR-161-suggestions-proposals-approval-grants-undo.md) | Suggestions, proposals, approval grants and Undo as a compensating event; the policy actor is dormant | red | accepted |
| [ADR-162](ADR-162-client-withdrawal-unaccepted-uploads.md) | A client may withdraw an upload the firm has not accepted - void and hide at once, crypto-erase by detached key after 30 days unless held | red | accepted |
| [ADR-163](ADR-163-white-label-portal-domains-branded-email.md) | White-label portal: neutral portal domain that never contains "accrued", same-origin `/v1`, the host as a branding hint only, per-firm branded email | amber | accepted |
| [ADR-164](ADR-164-independence-attest-client-rules.md) | Independence and attest-client rules: a derived attest flag, G2 on assignment, sign-off and client-facing actions for attest clients only, an SKE designee and NAS evaluation, no GL posting and no policy principal | red | accepted |
| [ADR-165](ADR-165-staff-session-bff.md) | Staff session BFF: three pre-session `/v1/auth` routes on the ROUTE-001 list, global sessions behind definers, cookie rotation with reuse detection, 30-minute idle and 12-hour absolute limits | red | accepted |
| [ADR-166](ADR-166-citation-v2-number-provenance.md) | Citation v2 and number provenance - ten verified kinds, verify before display, quote hash only, moved and broken from insert-only events, relink as a human act | red | accepted |
| [ADR-167](ADR-167-tri-pii-field-flags-gateway-tin-refusal-consent-gate-shape.md) | TRI, phi and pii_kind field flags beside the four classification levels; the gateway refuses TIN patterns in model context; the shape of the section 7216 consent gate | red | accepted |
| [ADR-168](ADR-168-portal-opaque-sessions.md) | Portal sessions: opaque access tokens checked against `auth_sessions`, pinned to tenant and host, after the portal's own email code (an exception to ADR-020 for portal clients) | red | accepted |
| [ADR-169](ADR-169-canonical-run-states-durable-run-records-c6-v1.md) | Canonical agent run states with the legacy status map; decision-relevant run records persisted at completion under engagement retention; the C6 v1 stub shape | red | accepted |
