---
id: SPEC-000
title: Walking skeleton
status: approved
owner: Founder
risk_zone: red
related_adrs: [ADR-002, ADR-004, ADR-005, ADR-007, ADR-011, ADR-013, ADR-014, ADR-016, ADR-017, ADR-018, ADR-019, ADR-021, ADR-022, ADR-023, ADR-024, ADR-027, ADR-029, ADR-031, ADR-035, ADR-037, ADR-038, ADR-042, ADR-047, ADR-051, ADR-054, ADR-065, ADR-066, ADR-070, ADR-083, ADR-090, ADR-101]
related_specs: []
created: 2026-10-04
updated: 2026-10-05
---

> **Instructions for coding agents**
> - The features here are deliberately trivial. **The purpose is the patterns.** Every pattern built here becomes the reference implementation all later code copies, so build each one exactly as its ADR specifies — no shortcuts, no placeholders in red-zone code.
> - Implement only what this spec describes. If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*.
> - Every test must reference the acceptance criterion it proves.
> - Almost every path here is protected. Each task needs an approval file from the founder.

## 1. Summary
A firm user signs in, creates an engagement and adds one request item. A fake connector retrieves a trial balance, which becomes an immutable evidence version with full provenance. A screening step runs through the AI gateway against a fake model. The item appears on a minimal evidence board. Every step is authorised, tenant-isolated and audit-logged.

## 2. Problem and context
Coding agents replicate whatever patterns exist. Before any feature work, every architectural pattern must exist once, correctly, end to end, so later features copy proven code rather than inventing their own.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Firm staff user | Signs in, creates an engagement, adds a request item, triggers retrieval, views the board |
| Firm admin | Sees engagement metadata only (ADR-024) |
| Reviewer | Can view, cannot add request items |
| System actor | Runs retrieval through the fake connector |
| Agent actor | Runs screening through the gateway; proposes only |

## 4. Goals and non-goals
**Goals**
- Establish every pattern listed in §22
- Deploy to staging through Terraform with every CI stage 1–2 gate green

**Non-goals**
- Real ledger connector, real model calls
- Client portal, client users, connections UI
- Uploads, matching, follow-ups, export, engagement agent
- SSO administration UI (sign-in only)
- Styling beyond design-system defaults

## 5. User stories and acceptance criteria

### Story 1: Sign in to my firm
- **AC-1** Given a user with a membership in Firm A, when they sign in through the identity provider, then they land in Firm A's context and the request context carries Firm A's tenant ID resolved from the membership.
- **AC-2** Given a signed-in user with no membership, when they call any engagement endpoint, then the response is 403 and no data is returned.
- **AC-3** Given a user whose membership is revoked, when they make their next request with an otherwise valid token, then it is denied.

### Story 2: Create an engagement
- **AC-4** Given a firm staff user with permission, when they create an engagement with a client, one client entity and a fiscal period, then it is stored with Firm A's tenant ID, an audit event is written in the same transaction, and the creator becomes an engagement member.
- **AC-5** Given an engagement in Firm A, when any Firm B user lists or fetches engagements, then Firm A's engagement never appears — via the API, the repository, or a direct query with Firm B's tenant session.
- **AC-6** Given a firm admin who is not an engagement member, when they view the engagement, then they receive metadata only (name, status, team, fiscal period) and content endpoints return 403.

### Story 3: Add a request item
- **AC-7** Given an engagement member with permission, when they add a request item with description and audit area, then it is stored with status `open` and an audit event is written.
- **AC-8** Given a reviewer on the engagement, when they attempt to add a request item, then the response is 403.

### Story 4: Retrieve a trial balance
- **AC-9** Given a request item and a fake connection on the client entity, when retrieval is triggered, then a Temporal workflow runs the six pipeline stages as activities: the raw payload is stored write-once under its SHA-256 fingerprint and encrypted with Firm A's key; it is normalised into the common ledger model with source identifiers; control totals pass; an immutable ledger snapshot is written.
- **AC-10** Given a validated snapshot, when rendering runs, then an evidence item and evidence version are created with a deterministic spreadsheet file, provenance (source, method `retrieved`, pull time, period, entity, fingerprint), and a fulfilment linking the version to the request item with `created_by_kind = rule`.
- **AC-11** Given the fake connector returns a trial balance whose debits do not equal credits, when retrieval runs, then the sync run is marked failed validation and no evidence version is created.
- **AC-12** Given the same snapshot rendered twice, when fingerprints are compared, then they are identical.
- **AC-13** Given an existing evidence version, when any code attempts to update or delete it, then the database rejects the operation.

### Story 5: Screen the evidence
- **AC-14** Given a new evidence version, when screening runs through the AI gateway with the fake model, then a screening result is stored containing action, confidence, rationale, structured citations and unverified items, and is attributed to an agent actor.
- **AC-15** Given the fake model returns a citation to a cell that does not exist, when the handoff is verified, then that citation is marked unverified.
- **AC-16** Given any gateway call, when it completes, then a usage record is written with firm, engagement, agent, prompt version, tokens and cost.
- **AC-17** Given an agent context, when it attempts to accept the evidence version, then the operation is refused.

### Story 6: See it on the board
- **AC-18** Given the engagement, when a member opens the evidence board, then the request item shows source `Retrieved`, its status, and its screening result; agent rationale is rendered as sanitised plain text.

### Story 7: It runs safely in staging
- **AC-19** Given the retrieval workflow, when its recorded history is replayed against the current code, then replay succeeds.
- **AC-20** Given the repository, when `make check` runs, then every stage 1 and 2 gate passes.
- **AC-21** Given a merge to main, when the pipeline runs, then the same image is deployed to staging via Terraform and the flow in Stories 1–6 works there.

## 6. Behaviour and flows
**Happy path**
1. User signs in → membership resolved → tenant context built.
2. User creates engagement → unit of work writes engagement, membership, audit event, outbox event.
3. User adds request item.
4. User clicks *Retrieve trial balance* → API signals a workflow → activities: extract (fake connector) → raw → normalise → validate → snapshot → render → fulfilment.
5. Domain event `evidence_version.created` → screening workflow → gateway → fake model → handoff verification → screening result.
6. Board shows the item.

**State transitions**
| From | Event | To | Who |
|---|---|---|---|
| request_item: open | fulfilment created by rule | received | System |
| request_item: received | screening completed | ready_for_review or needs_revision | Agent (proposal) |
| sync_run: running | control totals fail | failed_validation | System |

## 7. Domain and data changes
- **Entities:** firms, users, memberships, clients, client_entities, engagements, engagement_members, request_lists, request_items, connections, sync_runs, ledger_snapshots, trial_balance_lines, evidence_items, evidence_versions, provenance, fulfilments, screening_results, agent_runs, usage_records, audit_events, outbox.
- **Invariants:** every tenant table has `tenant_id NOT NULL` with row-level security; `evidence_versions` and ledger tables are insert-only for the application role; `audit_events` insert-only; `review_decisions` (created but unused) constrained to human actors.
- **Migrations:** initial schema; reversible.
- **Retention:** default policy record only; deletion not in scope.

## 8. Interfaces
| Method | Path | Action | Purpose |
|---|---|---|---|
| GET | /v1/me | — | Current user, memberships, active tenant |
| POST | /v1/engagements | engagement.create | Create engagement |
| GET | /v1/engagements | engagement.read_metadata | List (filtered by `visible`) |
| GET | /v1/engagements/{id} | engagement.read_metadata / engagement.read | Metadata or full view |
| POST | /v1/engagements/{id}/request-items | request_item.create | Add request item |
| GET | /v1/engagements/{id}/request-items | request_item.read | List with evidence and screening |
| POST | /v1/engagements/{id}/retrievals | connection.pull (system) via evidence.upload | Trigger retrieval |

Schemas defined in Pydantic; client generated (ADR-013).

## 9. Authorisation and tenancy
- Tenant from membership (ADR-002); `tenant_session(ctx)` everywhere (ADR-014).
- Actions above checked via `authorise`; lists via `visible` (ADR-027).
- Firm admin metadata-only (ADR-024).
- No client-side access in this spec.

## 10. AI behaviour
| Field | Value |
|---|---|
| Purpose | Screen a retrieved trial balance |
| Spec | `backend/src/abacus/modules/agents/specs/evidence.screener.yaml` |
| Prompt | `evidence.screen@v0` |
| Inputs | Request item description; computed summary of the trial balance (totals, period, entity) — never raw rows (ADR-050) |
| Untrusted inputs | Account names from the connector |
| Output schema | `ScreeningOutput(Handoff)` |
| Tier | small (fake model in this spec) |
| Cost budget | $0.03 per call |
| Autonomy | propose |
| Failure | invalid output → one repair → escalate |
| Evaluation | suite scaffolded with three synthetic cases; real evaluation deferred |
| Logged | model, prompt version, inputs hash, output |

## 11. Integrations
Fake connector only, implementing the full contract (ADR-037) and passing the conformance suite.

## 12. Edge cases
- Membership revoked mid-session (AC-3)
- Unbalanced trial balance (AC-11)
- Retrieval triggered twice → idempotent; one snapshot
- Workflow worker restarts mid-pipeline → resumes without duplicates
- Fake model returns schema-invalid output → repair, then escalate
- Firm B guesses Firm A's engagement ID → 404 without leaking existence

## 13. Security and privacy
- Ledger data and evidence: Restricted; engagement metadata: Confidential (ADR-031).
- Per-tenant key for raw payloads and evidence files (ADR-035).
- Threats: cross-tenant access, injection via account names, agent decision escalation — each covered by an AC.

## 14. Audit trail and evidence integrity
Audit events for engagement creation, membership, request item creation, sync run start and finish, snapshot, evidence version, fulfilment, screening result. Evidence versions immutable at database and storage layers.

## 15. Observability
Trace spans from API through workflow, activities and gateway with one trace ID. Structured logs with no Restricted fields. Error tracking with scrubbing.

## 16. Performance and scale
Not a goal. Fake trial balance of ~200 accounts.

## 17. UX
Three screens: sign-in redirect, engagement list and creation, evidence board for one engagement. Empty, loading and error states. Design-system defaults only.

## 18. Test plan
| AC | Type |
|---|---|
| 1–3 | integration, security |
| 4–8 | integration, security, generated permission tests |
| 9–13 | integration, property, workflow |
| 14–17 | integration (fake model), unit |
| 18 | frontend unit, one Playwright journey |
| 19 | workflow replay |
| 20–21 | CI, deploy smoke test |

## 19. Rollout
Staging only. No feature flags needed.

## 20. Open questions
- [ ] Identity vendor confirmed? (ADR-029; skeleton may use the vendor's development environment)

## 21. Future
Everything in Phase 2 of the build plan.

## 22. Patterns this spec must establish — reference implementations to write

On completion, write each to `docs/architecture/reference/` and update the matching skill:

| Reference doc | Pattern |
|---|---|
| `backend-module.md` | Module layout, layering, public API |
| `tenancy-and-authz.md` | Tenant context, `tenant_session`, `authorise`, `visible`, matrix tests |
| `unit-of-work.md` | Unit of work, audit events, outbox |
| `temporal-workflow.md` | Workflow, activities, versioning, replay test |
| `connector.md` | Contract, fake connector, pipeline stages |
| `evidence-storage.md` | Write-once storage, fingerprints, per-tenant keys, deterministic rendering |
| `ai-agent.md` | Spec, prompt registry, context builder, gateway, handoff, citation verification, metering |
| `frontend-feature.md` | Generated client, design system, states, sanitised agent text |
| `observability.md` | Tracing and logging helper |
