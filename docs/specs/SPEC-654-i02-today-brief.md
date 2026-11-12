---
id: SPEC-654
title: I-02 Today brief (SHL-23, HOME-05) and the briefing.today capability
status: draft
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-233, ADR-230, ADR-234, ADR-169, ADR-166, ADR-160, ADR-145, ADR-167, ADR-232, ADR-148, ADR-235, ADR-143, ADR-063, ADR-050]
related_specs: [SPEC-027, SPEC-647, SPEC-653]
created: 2026-11-12
updated: 2026-11-12
epic: I-02
task: I-02-T01 (TASK-7609)
---

# SPEC-654 · Today brief

> **Instructions for coding agents**
> - This is chapter 09 §9.4.4's "record as a spec", the SPEC-027 follow-on: SPEC-027 deferred "the
>   narrative daily briefing" (its lines 28, 94, 222) and ADR-063 promised it ("Managers receive a
>   daily briefing…"). The design is `docs/plan/epics/I-02.md` §1 to §8; rows are
>   `docs/plan/epics/I-02.tasks.csv`. The acceptance criteria are the epic's §3 stories (3.1 to
>   3.10) and invariants (§3.11), adopted verbatim as the spec of record; this file lists them,
>   settles Q1 to Q4, and records what upstream shipped. Where they differ, this file wins.
> - Contract: `docs/contracts/today.md` (I-02-T03). Screen contracts: `docs/screens/SHL-23.md`,
>   `docs/screens/HOME-05.md` (I-02-T02).

## Scope
- Two P0 screens: **SHL-23** Today brief panel (the full frame and the seven-panel state board:
  1 default, 2 drill-in, 3 ask, 4 Margaret, 5 Late Dec 1, 6 quiet day, 7 building) and **HOME-05**
  Home with Today brief (a–f). Plus the DF-04 boundary and consent states, flag-off, history and a
  read-only past brief, and the per-card "summary unavailable" fallback.
- **What code composes and what the model writes.** Code composes every count, the fact paragraph,
  card order, highlighted rows, Needs you first, the groups, the drill-in and the assign prefills.
  The model (`briefing.today` v1, one turn, no tools) writes only per-engagement prose: the why
  lines, the drill-in summary and the risk line, each verified before display (INV-2) and facts by
  reference (ADR-230). No count ever comes from model output (I-COUNT).
- Modules: `practice` (amber: `practice/today/` read model and routes), `agents` (red:
  `daily_briefings`, `agents/briefing/` collector, step, validator, dispatch; the spec and prompt),
  `engagements`, `requests`, `tax` (amber: attention providers, work-item hooks), `workbench`
  (the `today_brief` context kind). `review` and `collaboration` are read only.
- Out of scope: the portfolio brief (Q6, PH7), "Brief settings…", saved prompts in the composer
  (W-03, DF-32), A-08's flux attention item and A-09's Late provider (fixtures until then), real
  firm data (Q7).

## Decisions and ADRs (the acceptance check)
| Epic ID | Repository ADR | Status on main | What I-02 relies on |
|---|---|---|---|
| P-22 (AG-01), "ADR-157" | ADR-233 Agent capabilities and definitions | proposed | `briefing.today` spec v2 in code |
| P-24 (AG-05), "ADR-160" | ADR-230 Structured agent output | accepted | `AgentBlocks`, numbers by reference |
| P-46 (AG-02), "ADR-158" | ADR-234 Gateway conversations and tool use | proposed | `converse()`; no token streaming |
| P-47 (AG-03), "ADR-147" | ADR-169 Canonical run states, durable run records | accepted | a briefing is an AgentRunWorkflow run |
| P-48 (AG-07), "ADR-144" | ADR-166 Citation v2 and number provenance | accepted | verified before display |
| P-07, "ADR-133" | ADR-160 Review grammar | accepted | `human_gates`, the one count source (C13) |
| P-06, "ADR-118"; DEC-43 | ADR-145 Generalised `visible()` scope kinds | accepted | walls, no hidden counts |
| P-12 (AG-16), "ADR-146" | ADR-167 TRI and PII flags, consent gate shape | accepted | `consent_7216`, C19 |
| P-15 (AG-06), "ADR-156" | ADR-232 Real time via SSE | proposed | Building → Ready over `/v1/events` |
| P-28 (AG-15), "ADR-204" | ADR-148 Entitlements, agent-minutes, budgets | accepted | metering; flags carry rollout only |
| P-23 (AG-04), "ADR-159" | ADR-235 Workbench sessions (amends ADR-063) | proposed | the ask binding |
| P-37, "ADR-127" | ADR-143 Clock, scenario, synthetic marker | accepted | demo clock, scenarios |
| DEC-71 (P-14) | retention per record type | decided | `daily_briefing` 90 days (Q3) |

ADR-232 to ADR-235 stay proposed (DEC-3016, Ayush's acceptance); I-02 builds on them as P-10 and
W-02 do. ADR-235's amendment of ADR-063 and `build-plan.md` covers "Managers receive a daily
briefing…": the brief is code over the human-gate projection plus verified per-engagement prose.

## Settled questions (DEC-4608)
- **Q1 production layout.** HOME-05 a/d, composed by code: Needs you first and groups by
  deterministic rules, per-engagement text from the model, and the code fact paragraph in place of
  HOME-05 a/d's model-voiced lead (a recorded deviation). `layout=by_engagement` (HOME-05 f) is
  built as the fallback.
- **Q2 builds.** On first open of the day (HOME-05 e's building state), never on the
  EngagementAgent's 09:00 tick: no edit to the protected `engagement_agent_workflow.py`. Revisit if
  first-open p95 exceeds 20 s for two weeks.
- **Q3 retention.** 90 days, record type `daily_briefing`, not decision-relevant; run records keep
  their own retention.
- **Q4 Today threads in WB-01.** Yes: one session per viewer per day under Mine with a
  "Today · <date>" chip, so a question can continue in Workbench.
- **Q5** (HOME-05 d's "Signatures"): I-01's DF-25 taxonomy is used verbatim; if the band is
  "Approvals & sends", HOME-05 d's label is a recorded deviation, never a second taxonomy.

## Inventory of what upstream shipped (2026-11-12, main 09639107a)
- **I-01:** `practice/home.py` and `home_contract.py` (`GET /v1/home`), the C13 gate half in
  `review` (`human_gates`, `GET /v1/human-gates/counts`), HOME-01 live with the "Open Today →"
  link already behind `today_brief.enabled` (no such flag existed: I-02-T04 creates it).
- **P-10:** AgentRunWorkflow, `converse()`, spec v2, context v2, eval infrastructure,
  `/v1/events`, the capability endpoint, the agent-minute ledger.
- **P-05:** to-dos and SHL-17 (`?ov=todos:new:<nonce>`). **P-04:** decision cards, SHL-11 and SHL-12.
- **W-02 (S40):** SPEC-653, the workbench-sessions contract stub, `workbench.enabled`. The ask
  binding waits for `workbench.assistant` (W-02-T12) and session workflow v2 (W-02-T15).
- Not yet built: `practice/today/`, `daily_briefings`, the collector, the capability, the
  attention-provider slot, the screens.

## Endpoints (I-02 §4.3; `AbacusRouter`, one action each)
| Method · path | Module | Action | Row |
|---|---|---|---|
| `GET /v1/me/today?date=` | practice | `briefing.read` | stub T03, live T10 |
| `POST /v1/me/today/builds` `{date, mode}` | practice → agents | `briefing.rebuild` | T03, T13 |
| `GET /v1/me/today/work-items/{work_item_id}?date=` | practice | `briefing.read` | T03, T10 |
| `GET /v1/me/today/history?before=&limit=` | practice | `briefing.read` | T03, T16 |
| `GET /v1/me/today/history/{brief_id}` | practice | `briefing.read` | T03, T16 |
| `POST /v1/me/today/questions` `{text, brief_id}` | agents / workbench | `briefing.ask` | T03 shape, T14 |

Every route reads only the caller's own brief (`viewer_user_id = caller`), answers 404 while
`today_brief.enabled` is off, and never returns a hidden or walled count (DEC-43).

## Flag, matrix, table
- Flag `today_brief.enabled` (I-02-T04): boolean, default false, owner notanaskhan; the repository
  calendar's created 2026-11-12 and expires 2027-05-07 under DEC-137 (the epic's 2028 dates are
  plan dates). Retired into Home at I-02-T22.
- Matrix (I-02-T04): `briefing.read`, `briefing.rebuild`, `briefing.ask`; every firm role allow;
  client roles, platform support and the agent deny.
- `MODULE_DEPENDENCIES`: `practice` may import `review`, `agents` and `requests`; nothing imports
  `practice`.
- Table `daily_briefings` (I-02-T06, `agents`, 0850+): scope `engagement` or `user`, terminal rows
  immutable, identifiers only for the user scope, no TIN or quoted document text.

## Acceptance criteria (the epic's §3, verbatim there; AC-1 to AC-11 below are 3.1 to 3.11)
- **AC-1 · 3.1 Counts equal Home** (I-COUNT): Daniel 3 · 6 · 2 · 0 = 11; Margaret 2 · 0 · 2 · 0 = 4; cells
  open HOME-02 filtered; Overdue derived, a subset; no count from model output.
- **AC-2 · 3.2 The fact paragraph**: code-composed sentences from registered facts.
- **AC-3 · 3.3 Engagement briefings**: model why lines, drill-in summary, risk line; verified, by reference.
- **AC-4 · 3.4 Needs you first** and **AC-5 · 3.5 Groups**: deterministic order and grouping rules.
- **AC-6 · 3.6 Drill-in and Assign open items**: SHL-17 prefill; reserved items not assignable.
- **AC-7 · 3.7 Ask about your day**: read-only `workbench.assistant` turns bound to the day's brief.
- **AC-8 · 3.8 Building, quiet day, rebuild, history**; **AC-9 · 3.9 docked, collapsed, drawer, flag-off**;
  **AC-10 · 3.10 unavailable AI, consent, metadata-only viewers and walls (DF-04, INV-3)**.
- **AC-11 · 3.11 Invariants:** INV-1, INV-2, INV-3, INV-4, INV-5 and I-COUNT with the tests the epic names.

## S40 rows
T01 (this), T02 screen contracts, T03 Today contract stub, T04 protected bundle, T05 consumer
contract tests, T06 migration `daily_briefings`. T07 onward are S41 to S43.
