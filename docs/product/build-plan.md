# Build plan

> **Instructions for coding agents**
> - Work only on the current sprint's scope. Scope comes from the Accrued catalogue, journeys and ADRs in `docs/plan/`: order and dates in `docs/plan/01-strategy-roadmap.md`, the sprint in `docs/plan/07-sprint-plan.md`, tasks in `docs/plan/backlog.csv`.
> - This file keeps the principles, the pilot protocol and how every increment runs. ADRs define *how*. Specs define *exactly what*.
> - If a task seems to need something from a later sprint, build the minimal contract stub or note it in the task file, and carry on.

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

## 3–6. Phases, foundations and product increments

Replaced by the Accrued plan: phases PH0–PH7, sprints S0–S74 and 74 epics in `docs/plan/01-strategy-roadmap.md` (§1.0 order, §1.2 dates) and `docs/plan/07-sprint-plan.md`. What is already built is in `docs/plan/status/`.

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

Replaced by the Accrued plan: see `docs/plan/01-strategy-roadmap.md` for the phases after the pilots.

---

## 11. How every increment runs

1. Spec written from the epic in `docs/plan/epics/`, with design-partner input where the plan calls for it; open questions decided with the plan's default and recorded.
2. A coding session writes the plan into the task file first (amber and red), then builds.
3. Tasks sliced to one session each.
4. Acceptance tests written first, from the acceptance criteria.
5. Implementation, then `make check`.
6. Optional self-review with the reviewer agents for amber and red.
7. Merge on a green `make check`.
8. Deploy to staging once at sprint close; demonstrate end to end.
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
| Gold-plating | Phases 1–2 | The test in principle 8; a written plan in the task file |
