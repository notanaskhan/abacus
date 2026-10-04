# Build plan

> **Instructions for coding agents**
> - This plan defines *what is built in which order*. ADRs define *how*. Specs define *exactly what*.
> - Work only on the current phase and increment. Never build ahead of the plan.
> - If an increment seems to require something from a later phase, **stop** and raise it.

This plan has no dates. Progress is gated by evidence, not the calendar: each phase ends when its exit criteria are met.

---

## 1. Principles

1. **Thin vertical slices.** Every increment works end to end on staging and can be demonstrated.
2. **Ordered by risk, then by need.** The assumptions most likely to kill the company are tested first.
3. **Validate before building past the skeleton.** The skeleton is independent of discovery; nothing after it is.
4. **Foundations at production depth.** Anything expensive to retrofit, or required for trust and compliance, is built properly the first time.
5. **Knowledge-dependent features wait for knowledge.** Anything whose right design depends on how real firms and clients behave stays thin until real use shows the way.
6. **Two before general.** An abstraction proven by one implementation is a guess. Two connectors before the connector contract is frozen; two loop agents before the loop harness is generalised.
7. **Shadow before live.** The product runs alongside real engagements, relied on by no one, before any firm depends on it.
8. **Guard against gold-plating.** Every foundation investment must pass one test: *is it expensive to retrofit, or required for trust and compliance?* If neither, wait for evidence.

---

## 2. Two kinds of thin

| Built to full depth in Phase 1 | Deliberately thin until real data (Phase 5) |
|---|---|
| Tenancy and row-level security | Learning loop beyond capturing corrections |
| Permission matrix and generated tests | Firm rules from corrections |
| Audit trail and outbox | Engagement memory beyond basic facts |
| Immutable evidence, write-once storage, per-tenant keys | Firm memory and knowledge retrieval content |
| AI gateway: specs, registry, limits, metering, route abstraction | Evaluation datasets (infrastructure is full; cases come from use) |
| All four work classes and admission control | LLM planner and autonomy level 2+ |
| Data classification tags and output controls | Portfolio agent |
| Citation verification | Command bar |
| Evaluation infrastructure: runner, graders, calibration | Loop-harness generalisation (until a second loop agent) |
| Synthetic company generator | |
| Full observability: dashboards, SLO alerting, canary firm | |
| Backups, cross-region copies, completed restore drill | |
| Break-glass tooling | |
| Security operations baseline | |
| CI stages 1–5, including mutation testing on red-zone modules | |
| SOC 2 Type I and a penetration test before any client connects | |

---

## 3. Phase overview

| Phase | Purpose | Ends when |
|---|---|---|
| **0. Validate and co-design** | Prove the riskiest assumptions; secure design partners | Discovery thresholds met; partners signed; ledger chosen |
| **1. Foundations** | Every platform primitive at production depth | Skeleton and primitives complete, all gates green |
| **2. Product increments** | The product, slice by slice | All increments demonstrated on staging |
| **3. Shadow pilot** | Run alongside real engagements, relied on by no one | Shadow thresholds met |
| **4. Live pilot** | Firms rely on it at autonomy level 1 | Pilot success criteria met |
| **5. Deepen from real data** | Build what only real use can design | Ongoing |

Phase 0 and the start of Phase 1 run in parallel: the walking skeleton uses a fake connector and fake model, so it depends on no discovery answer.

---

## 4. Phase 0 — Validate and co-design

### 4.1 Discovery

**Who:** 15–20 conversations across audit partners, managers and seniors at US regional firms below the top 100, and controllers at companies that are audited.

**Questions:**
- Across your audit clients, roughly what share run each ledger? (QuickBooks Online, QuickBooks Desktop, NetSuite, Sage Intacct, Dynamics, other)
- How many hours per engagement go to request management, by grade?
- What share of evidence is in hand on the first day of fieldwork?
- What does a typical request list look like? (collect real lists, anonymised)
- *Controllers:* Would you grant your auditor read-only access to your ledger if it saved you weeks of assembling documents? What would you need to see first?
- *Partners:* Would you accept evidence pulled directly from the client's ledger? What would make you trust it?
- What would you pay, and how do you budget for audit tools?

**Retrievability tagging:** tag every line of at least ten real request lists by tier (A–E, see glossary) and compute the retrievable share (tiers A–C).

**Decision thresholds — set these before the first call and record them here:**
- Minimum retrievable share to proceed: `____ %`
- Minimum share of controllers willing to grant access: `____ %`
- Minimum share of partners willing to accept retrieved evidence: `____ %`

If thresholds are missed, stop and reconsider the wedge before Phase 2.

**Outputs:** `docs/product/discovery/` — ledger distribution table, tagged request lists, access and acceptance findings, pain metrics, pricing signals.

### 4.2 Choose the first ledger

From the ledger distribution (ADR-045). Submit the provider's production access application immediately; it gates Phase 2.

### 4.3 Design partners

**Target:** two or three.

**Criteria:**
- US regional firm, below the top 100
- Primarily private company audits
- Audit clients on the chosen ledger
- A senior manager champion
- Willing to do a prior-year replay and a shadow pilot
- Some audit clients with non-December year-ends (see §9)

**Agreement covers:** consent for data use including evaluation datasets, confidentiality, feedback cadence, case study rights, pricing for later phases.

### 4.4 Prior-year replay

The single strongest validation available. With firm and client consent, run the product against an engagement the firm has *already completed*.

**Two routes:**
- **Live connection** to the client's ledger for the prior fiscal year — requires the client's authorisation.
- **From the firm's archive** — using ledger exports and evidence files already in the completed engagement file.

**Measures:**
- What share of the actual request list retrieval would have covered
- Screening agreement with what auditors actually accepted, with the dangerous-error rate reported separately
- Matching accuracy against known fulfilments

**By-product:** a consented, de-identified, labelled evaluation dataset, stored outside the repository (ADR-081).

The replay can run once Phase 2 increments 1–6 exist, but its consent and data arrangements are secured in Phase 0.

### 4.5 Co-design

Walk design partners through the evidence board, the client consent screen, item detail, follow-up drafts and the export package. Record changes as spec inputs.

### 4.6 Business and legal setup

- Check the founder's employment agreement for IP and non-solicit conflicts
- Form the Delaware company
- Engage a CPA advisor with audit experience
- Counsel: master agreement, data processing agreement, breach notification templates and timelines (ADR-097), privacy obligations (ADR-034)
- Insurance: cyber and professional liability
- Start SOC 2 Type I in the compliance tool
- Model provider terms: zero retention and no training (ADR-031)

### Phase 0 exit criteria

- [ ] Discovery thresholds met (or wedge consciously revised)
- [ ] First ledger chosen; production access application submitted
- [ ] Design partners signed with consent arrangements in place
- [ ] Legal and insurance in place
- [ ] Discovery outputs committed to `docs/product/discovery/`

---

## 5. Phase 1 — Foundations

### 5.1 Order of work

1. **Repository and docs pack** — ADRs, glossary, templates, permission matrix
2. **Agent configuration** — constitution, reviewer agents, hooks, protected paths, skill files
3. **CI stages 1 and 2** and `make check`
4. **Synthetic company generator** — powers tests, evaluations, staging, load tests and demos; built first because everything after depends on it (ADR-085)
5. **Walking skeleton** (SPEC-000)
6. **Platform primitives to production depth** (§5.3)
7. **CI stages 3–5**
8. **Operations baseline** (§5.4)

### 5.2 Walking skeleton — SPEC-000

**The flow, deliberately trivial:** a firm user signs in, creates an engagement, adds one request item. A fake connector retrieves a trial balance, which becomes an evidence version with full provenance. A screening step runs through the AI gateway against the fake model. The item appears on a minimal evidence board. Every step is audit-logged.

**Patterns it must establish:**

| Pattern | ADRs |
|---|---|
| Sign-in via identity vendor; membership-based tenant context | 002, 029 |
| `authorise`, `visible`, matrix-generated tests | 023, 027 |
| Row-level security with the application role | 014 |
| Unit of work, outbox, audit events | 007, 018 |
| Temporal workflow and activity, replay test, versioning | 017, 090 |
| Connector contract via fake connector, conformance suite | 037 |
| Six-stage pipeline, minimal | 038 |
| Write-once evidence storage, per-tenant keys | 016, 035 |
| AI gateway: spec, prompt registry, context builder, fake model, cost record | 019, 047, 051 |
| Handoff schema with citation verification | 054, 066 |
| Output controls on agent text | 065 |
| React page with design-system components and generated client | 011, 013 |
| Tracing and logging helper | 022 |
| Classification tags | 031 |
| Terraform deploy to staging | 021 |
| CI stages 1–2 green | 083 |

**Exit criteria:**
- [ ] Deployed to staging; every gate green
- [ ] Reviewed line by line by the founder
- [ ] Each pattern documented as a reference implementation in `docs/architecture/reference/`
- [ ] Skill files updated from the real code

### 5.3 Platform primitives at production depth

| Layer | Production depth means |
|---|---|
| **Data** | Connector contract and conformance suite; fake connector; full pipeline; evidence store; common ledger model v1 with source identifiers and authorship (ADR-039) |
| **Context** | Engagement graph; methodology configuration v1 (firm templates import); knowledge retrieval infrastructure (pgvector) without content |
| **Execution** | Temporal infrastructure; workflow patterns; agent harness for workflows and a minimal loop; all four work-class queues; admission control (ADR-071, 072) |
| **Trust** | Review queues; audit trail; evaluation runner, graders and calibration tooling; citation verifier; output controls; outbound message scope checker |
| **Learning** | Storage of corrections and reason codes only |
| **Collaboration** | Identity vendor integration; firm and engagement roles; client invitations; notifications; client view shell; ethical walls |
| **Foundation** | Tenancy and row-level security; per-tenant keys; classification tags; metering; budget hierarchy (ADR-069); model route abstraction with second route configured (ADR-073) |

### 5.4 Operations baseline

- Terraform for local, staging and production accounts (ADR-087)
- Build-once promotion with health-checked rollouts (ADR-088)
- Feature flag registry (ADR-089)
- Dashboards and SLO alerting (ADR-093, 094)
- Backups, point-in-time recovery, cross-region copies; **first restore drill completed** (ADR-096)
- Break-glass tooling (ADR-028)
- Security operations baseline (ADR-099)
- Status page
- Runbooks drafted for every scenario in ADR-098

### Phase 1 exit criteria

- [ ] Skeleton exit criteria met
- [ ] All primitives at the depth in §5.3
- [ ] CI stages 1–5 running, including mutation testing on red-zone modules
- [ ] Operations baseline complete, restore drill passed
- [ ] Runbooks drafted

---

## 6. Phase 2 — Product increments

Each increment is one spec, several tasks, one demonstration on staging.

| # | Increment | Delivers | Depends on |
|---|---|---|---|
| 1 | **Engagement setup** | Engagement with entities and fiscal period; request list import from Excel; request items and audit areas; engagement team roles; client contact invitations | Phase 1 |
| 2 | **Client portal and connection** | Branded invitation; passwordless client login; connection flow for the first ledger with honest consent copy (ADR-040); access log; connection health | 1; provider sandbox |
| 3 | **Retrieval — first ledger** | Trial balance, GL detail, journal listing, agings, customers and vendors; control totals; snapshots; deterministic rendering; evidence items. **Canary firm** set up against the provider sandbox (ADR-094) | 2 |
| 4 | **Second ledger connector** | Second-most-common ledger from discovery, through the same contract. **Connector contract frozen afterwards**; ADR-037 amended if the second connector revealed changes | 3 |
| 5 | **Classification and evidence board** | Tiers from connection capabilities, rules first with model fallback; automatic fulfilment of retrievable items; evidence board with statuses, filters, and the "retrieved, never asked" count | 3 |
| 6 | **Uploads, matching and screening** | Client uploads for request-tier items; email reply matching; matcher; screener; item detail with provenance, results and verified citations; accept, reject, send back with reason codes | 5 |
| 7 | **Export** | Binder-ready package with index, provenance and audit trail; fresh MFA (ADR-036) | 6 |
| 8 | **Follow-ups and engagement agent v1** | Drafted follow-ups with approval; long-running engagement agent with deterministic policies; autonomy levels 0–1; activity feed; daily briefing; pause switches (ADR-058–063) | 6 |
| 9 | **Change detection** | Scheduled syncs; snapshot comparison; change events; new versions; re-review flags (ADR-041) | 3, 8 |
| 10 | **Sample support** | Sample selection import; support-finder loop through the harness; found, not found, doubtful; requests for not-found items | 3, 8 |
| 11 | **Measurement and comparison** | Instrumentation and reports for every shadow and pilot metric; side-by-side comparison of product output against the firm's actual process | 1–10 |

**Prior-year replay** (§4.4) runs as soon as increments 1–6 exist, and its results feed the evaluation suites before increments 7–11.

### Phase 2 exit criteria

- [ ] Every increment demonstrated end to end on staging
- [ ] Prior-year replay completed with results recorded
- [ ] Evaluation suites for classifier, matcher, screener and support finder at agreed thresholds
- [ ] Busy-season load test passed at target volumes (ADR-075)

---

## 7. Phase 3 — Shadow pilot

### Entry gate

- [ ] Penetration test completed and findings resolved
- [ ] SOC 2 Type I report in hand
- [ ] Data processing agreements signed; client consents obtained
- [ ] SLO alerting, canary firm and status page live
- [ ] Second model route active (ADR-073)
- [ ] Restore drill passed within the last quarter

### Protocol

- The firm runs the engagement exactly as it always does, and relies on nothing the product produces.
- With the client's consent, the product connects to the ledger, retrieves, classifies and screens.
- Evidence the firm receives through its existing channels is copied into the product for matching and screening.
- Follow-ups are drafted but **never sent**. Autonomy level 0. No client-facing messages.
- Weekly comparison sessions with the champion.

### Measures

- Retrieval coverage against the actual request list
- Screening agreement with auditor acceptance; dangerous-error rate reported separately
- Matching accuracy
- Time from connection to first retrieved item
- Estimated hours the product would have saved
- Data freshness and connection health
- Incidents and override reasons

**Shadow thresholds — set before the shadow pilot starts:** `________`

### Phase 3 exit criteria

- [ ] Shadow thresholds met across at least two engagements
- [ ] No unresolved SEV1 or SEV2 incidents
- [ ] Champion confirms readiness to rely on the product

---

## 8. Phase 4 — Live pilot

### Protocol

- Autonomy level 1 (ADR-061)
- Client portal live; follow-ups sent with approval
- Evidence exported into the firm's binder
- Founder-led forward deployment: present for configuration, onboarding and issues

### Success criteria

| Metric | Tests |
|---|---|
| Share of invited clients who connect | Access risk |
| Share of request items retrieved without a request | Retrieval thesis |
| Time from connection to first retrieved item | The day-one moment |
| Evidence in hand on the first day of fieldwork, versus last year | Value |
| Share of retrieved items auditors accept | Evidence acceptability |
| Hours on request management per engagement | Return on investment |

**Kill or pivot signals:** low connection rate, low retrievable share, or low auditor acceptance — each means the wedge needs rethinking, not more features.

### Phase 4 exit criteria

- [ ] Success thresholds met
- [ ] Conversion to paid annual agreements (per pilot terms)
- [ ] Case study written from increment 11's reports

---

## 9. Choosing the season

Shadow and live pilots need real engagements in progress. Calendar-year audits cluster in January to March, but **firms also audit companies with June and September year-ends**, whose fieldwork falls outside the peak. Prefer design partners with some non-December year-end clients: it allows shadow pilots off-peak and reduces dependence on busy season.

If any live pilot work falls in January to March while features are still shipping, propose an ADR granting a year-one exception to ADR-092 at that point. Otherwise ADR-092 applies unchanged.

---

## 10. Phase 5 — Deepen from real data

Built only once real use shows their right design:

- Evaluation datasets from production feedback, firm-scoped (ADR-067, 081)
- Confidence calibration tuned on real outputs
- Firm rules from corrections, with approval and evaluation gates (ADR-068)
- Engagement and firm memory beyond basic facts (ADR-053)
- Knowledge retrieval populated with firm methodology documents (ADR-056)
- LLM planner and autonomy level 2 (ADR-060, 061)
- Loop-harness generalisation once a second loop agent exists; evaluate Pydantic AI or LangGraph per ADR-057
- Command bar and portfolio agent (ADR-063)
- Unified API for long-tail ledgers (ADR-045)
- Green-zone auto-merge once the reliability period is proven (ADR-086)
- Expansion along the product roadmap: testing, reporting and review modules; then tax and CAS products — CAS introduces ledger write access under new ADRs

---

## 11. How every increment runs

1. Spec written by founder and design partner; open questions empty.
2. A coding session writes the plan; founder approves (amber and red).
3. Tasks sliced to one session each.
4. Tests written from acceptance criteria in a separate session (ADR-078).
5. Implementation, then `make check`.
6. Reviewer agents; cross-model review for amber and red (ADR-084).
7. Founder review at the depth the risk zone requires.
8. Deploy to staging; demonstrate end to end.
9. Enable the flag for design partners.
10. Update docs, ADRs and skill files with anything learned.

**Definition of ready:** approved spec; empty open questions; external dependencies (provider sandbox, partner templates, consents) already in hand.

**Definition of done:** the task template's checklist, every gate green, demonstrated on staging.

---

## 12. Risk register

| Risk | Tested in | Mitigation |
|---|---|---|
| Controllers won't grant ledger access | Phase 0 discovery; Phase 4 connection rate | Honest consent copy; access log; read-only enforcement; request-mode fallback still delivers value |
| Retrievable share is too low | Phase 0 tagging; prior-year replay | Reconsider wedge before Phase 2 |
| Auditors distrust retrieved evidence | Phase 0 discovery; replay; shadow | Control totals, raw payloads, provenance on every file |
| Provider access approval delays | Phase 0 | Apply immediately; build against sandbox; second connector reduces dependence |
| Model behaviour drifts | Continuous | Pinned versions, evaluations, shadow comparisons, override monitoring (ADR-074, 082) |
| Security incident | Continuous | Phase 3 entry gate; ADR-097 process |
| Founder bandwidth | Continuous | Documentation, scoped on-call, operational help before the second busy season (ADR-100) |
| Gold-plating | Phases 1–2 | The test in principle 8; founder plan approval |
