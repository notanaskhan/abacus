---
id: SPEC-027
title: "Engagement agent v1: deterministic policies"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-005, ADR-025, ADR-040, ADR-058, ADR-059, ADR-060, ADR-061, ADR-062, ADR-063, ADR-090]
related_specs: [SPEC-011, SPEC-013, SPEC-015, SPEC-020, SPEC-022, SPEC-023, SPEC-024, SPEC-025]
created: 2026-10-10
updated: 2026-10-10
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Every engagement gets its **engagement agent** (ADR-058): a long-lived Temporal workflow from creation to archive (ADR-062). In v1 it runs **deterministic policies only**, the routine half of ADR-060, and makes **no model calls**. The platform retrieves and suggests by rule; agents screen and propose.

v1 has four parts:
- **overdue reminders:** items past their due date are chased, automatically or as drafts for a person, by autonomy level;
- **triggering:** retrieval, inbox matching and screening start from one place, by policy;
- **an activity feed:** what happened automatically on the engagement, by which policy, and why (ADR-063);
- **pause switches:** per engagement and per firm; pausing keeps state (ADR-062).

The planner (a daily planning step with a model) and the narrative briefing come later.

## 2. Problem and context
**Automatic reactions are scattered:**
- screening starts from an agents subscription on `evidence_version.created`;
- automatic retrieval is a connections policy;
- inbox matching runs when a file arrives;
- each checks autonomy and the engagement gate on its own.

**Other gaps:**
- Request items have **no due dates**, so nothing can be overdue, and nothing chases the client.
- Nothing records **what happened automatically and why**, and nothing can **pause** it.
- Autonomy stops at Routine (SPEC-024 Q3, "until the engagement agent exists"). The matrix already gives agents `follow_up.send` under `firm_setting(autonomy_policy)` ("routine reminders only"), but that condition isn't modelled, so it denies.

## 3. Actors
| Actor | Role here |
|---|---|
| Engagement agent (code) | Reacts to events and timers with v1's policies; acts under its initiator's authority (ADR-025) |
| Engagement partner, manager | Set due dates, pause and resume the engagement's agent, approve and send drafted reminders at Advise, read the feed |
| Senior, staff, reviewer | Read the feed; set due dates if they can update items (`request_item.update`) |
| Firm administrator | Pause and resume every agent in the firm (fresh MFA) |
| Client admin, contributor | Receive reminders by email in the firm's name; they never see the feed |

## 4. Goals and non-goals
**Goals**
1. **Lifecycle:**
   - started with the engagement (`engagement.created`), and started once for every existing non-archived engagement (Q7); it ends at archive;
   - domain events arrive as signals through the outbox, timers drive reminders, and history is bounded by continue-as-new;
   - workflow changes are versioned (ADR-090).
2. **Authority (Q1):**
   - the agent acts as an `AgentContext` whose initiator is the engagement's partner (the earliest-added active one);
   - every action is authorised by `authorise`, including the initiator intersection (ADR-025), walls and independence (TASK-045);
   - with no active partner, the agent pauses itself, with the reason in the feed.
3. **Policies**, each with an ID and version recorded on every feed entry:

   | Policy | When | Does | At Advise |
   |---|---|---|---|
   | **P-1 Screen** | New evidence version | Starts the screener (the existing workflow, now started by the agent) | Skipped, with the reason in the feed |
   | **P-2 Retrieve** | Connection created; an item classified as needing data; daily | Starts the platform's retrieval (a system run, by rule) | Skipped |
   | **P-3 Match** | A file waits in the inbox | Computes match suggestions (existing rule) and records them; never assigns | Suggestions still computed (they change nothing) |
   | **P-4 Remind** | An item is past its due date and still open or sent back | Chases the item's client assignee (or the client admins), batched to one email per contact per day, on the cadence in Q3; stops once the item is received, waived or accepted | Drafted for a partner or manager to send |
   | **P-5 Team digest** | Daily | In-app notification to the partner and managers: items overdue and reminders sent | Same |

   Every policy respects the engagement gate (no client-facing action until the engagement is open, SPEC-025), archive, and the pause switches. Agents never accept, reject, waive or confirm (ADR-005).
4. **Due dates (Q2):**
   - request items gain an optional due date;
   - the request list has a default due date that items without their own inherit;
   - set by people who can update items, in bulk on the Requests board, and shown on items and the Board.
5. **Reminders in the firm's name:**
   - a fixed template, no model: "Whitfield & Lane is still waiting for 3 items for their FY2026 audit of Halvorsen", followed by the item names and a link to the portal;
   - the sender's display name is the firm's (SPEC-025 AC-8);
   - each reminder is recorded (item, contact, sequence number, sent or drafted, at), so the caps hold across restarts.
6. **The activity feed (ADR-063):**
   - one insert-only row per automatic action: the policy and version, the action, the outcome (`done`, `skipped` with a reason, `drafted`, `failed`), links to the records touched, and when;
   - an **Activity** tab on the engagement for staff; clients never see it.
7. **Pause switches:**
   - **per engagement:** partner or manager, with an optional reason;
   - **per firm:** firm administrator, fresh MFA;
   - pausing stops every policy, including the platform's own retrieval for that engagement, and keeps state;
   - on resume, policies look at the current state once: evidence that arrived while paused is screened, and reminders resume on their next step without a burst;
   - the paused state shows in the engagement header, on Setup, and in the feed.
8. **Autonomy:**
   - Routine (level 1) lets the agent send routine reminders (P-4) automatically; Advise (level 0) drafts them for a person;
   - Manage and Portfolio stay unavailable until the planner exists.

**Non-goals**
- Any model call: the planner, the daily narrative briefing, model-drafted wording, the command bar.
- Specialist agents beyond the existing screener; agents ever deciding (ADR-005).
- Reminders by SMS or in the client portal (email only); reminders to staff by email (in-app only).
- Autonomy per engagement (per firm only in v1).

## 5. User stories and acceptance criteria
- **AC-1** Given an engagement is created, then its agent starts, and it ends when the engagement is archived. Existing non-archived engagements get one each, once.
- **AC-2** Given new evidence, then P-1 starts screening once per evidence version, at Routine, while not paused, and records it in the feed. At Advise, or while paused, it records `skipped` with the reason.
- **AC-3** Given an item is past its due date and open or sent back, the engagement is open and the agent isn't paused, then at Routine its contacts get at most one reminder email per day, listing their overdue items. Each item is chased at most the capped number of times (Q3), and no item that is received, waived or accepted is chased.
- **AC-4** Given Advise, then P-4 produces drafts. A partner or manager can send, edit the note, or dismiss them, and nothing is sent automatically.
- **AC-5** Given the engagement isn't open (SPEC-025) or is archived, then no client-facing action happens.
- **AC-6** Given a partner or manager pauses the engagement's agent, or a firm administrator pauses the firm's, then no policy acts until resume. On resume, evidence that arrived while paused is screened once, and reminders don't burst.
- **AC-7** Given any automatic action, then the feed holds its policy and version, outcome, reason and links. Staff with the engagement's read access see it; clients don't.
- **AC-8** Given the agent's initiator can't do an action (removed, walled, not independent, or not allowed by the matrix), then the action is refused at `delegation` and recorded as `failed`. With no active partner, the agent pauses itself.
- **AC-9** Given due dates, then items inherit the list's default unless set, people who can update items can set them in bulk, and the Board shows overdue items.
- **AC-10** Given every new screen (Activity tab, due dates, drafted reminders, pause controls), then loading, empty, error and not-allowed states exist, and colours come only from tokens.

## 6. Behaviour and flows
1. **Engagement created:** the agent workflow starts. It reads state, sets timers for the next due dates and the daily tick, and waits.
2. **A domain event arrives** as a signal. The matching policy checks, in order:
   - paused (firm, then engagement);
   - archived;
   - the engagement gate, for client-facing actions;
   - the autonomy level, read fresh each time;
   - `authorise` as the agent.

   It acts or records why it didn't.
3. **Daily tick, in the firm's time zone (Q3):** P-2's daily retrieval, P-4's reminders (batched per contact), and P-5's digest.
4. **Advise:** drafts appear on the engagement ("Reminders waiting for you"), where they can be sent, edited or dismissed.
5. **Pause:** a signal sets paused, and timers keep running without acting. On resume, one look at the current state.

## 7. Domain and data changes
- `request_items.due_on` (date, nullable) and `request_lists.default_due_on`.
- `engagement_agents`: engagement, workflow ID, `paused_at`, `paused_by`, reason, `self_paused_reason`.
- `firms.agents_paused_at` and `firms.agents_paused_by`.
- `agent_activity` (insert-only): engagement, policy, policy version, action, outcome, reason code, record links, at.
- `reminders`: item, contact, sequence, status (`drafted`, `sent`, `dismissed`), note, at.
- **Notifications catalogue:** `reminders.drafted` and `agent.digest`, to the partner and managers.

## 8. Interfaces
- `PUT /v1/engagements/{id}/request-items/due-dates` (bulk) and `PUT …/request-list/default-due-date`.
- `GET /v1/engagements/{id}/activity` (paged).
- `POST /v1/engagements/{id}/agent/pause` and `…/resume`; `POST /v1/firm/agents/pause` and `…/resume`.
- `GET /v1/engagements/{id}/reminders?status=drafted`, `POST …/reminders/{id}/send`, `POST …/reminders/{id}/dismiss`.

## 9. Authorisation and tenancy
New matrix actions (with the generated `_matrix.py`):
- `activity.read`: every staff engagement role, firm administrators and practice leaders;
- `agent.pause`: engagement partner and manager;
- `firm_agents.pause`: firm administrator, fresh MFA;
- `reminder.send`: partner and manager, for drafts.

Due dates use `request_item.update`.

**The agent's own grants:**
- task scope `screening.run`, `follow_up.draft` and `follow_up.send`;
- `follow_up.send` for agents is `firm_setting(autonomy_policy)`; modelling that condition in `authorise` (allowed at Routine and above) is an `identity/authz` change you approve by name (Q5).

All queries are tenant-scoped, and lists use `visible()`.

## 10. AI behaviour
None. No prompt, no model, no evaluation suite. The screener (P-1) is the existing agent, unchanged.

## 11. Integrations
Email through the existing transport, sent in the firm's name.

## 12. Edge cases and failure modes
- **The engagement is archived mid-reminder:** nothing is sent; the workflow ends.
- **A contact is removed:** their reminders stop. If no contacts are left, the feed says so, and the digest lists the item.
- **A due date changes:** the item's reminder sequence restarts from the new date.
- **Email bounces:** recorded on the reminder; no retry storm.
- **The worker restarts:** state is in Temporal and the tables; caps come from `reminders`.
- **Several partners:** the earliest-added active one is the initiator. If they're removed, the next takes over and the feed records the change.

## 13. Security and privacy
- Reminder emails contain item names and counts only, never evidence content.
- The feed holds references, never client content.
- Agents act within their initiator's rights (ADR-025).

## 14. Audit trail and evidence integrity
- Every automatic action is audited (actor kind `agent`, policy and version), as well as fed.
- Pause and resume, due-date changes, and sent or dismissed drafts are audited with the person.

## 15. Observability
- Counters per policy and outcome, and reminders sent or drafted.
- A gauge of agents paused, by scope.
- Workflow history length, and continue-as-new events.

## 16. Performance and scale
- One workflow per engagement.
- A daily tick per engagement, spread across the hour to avoid a thundering herd.
- Reminder batching keeps it to one email per contact per day per engagement.

## 17. UX
- An **Activity** tab, newest first, each entry in plain words: "Screened bank statement v2 (P-1). Proposed: needs revision", "Skipped reminders: engagement paused".
- **Due dates** on items and the Board, a default on the request list, and bulk set.
- **"Reminders waiting for you"** at Advise, on Setup and the engagement header.
- **Pause and resume** in the engagement header; the firm switch under Autonomy.

## 18. Test plan
| AC | Type | Notes |
|---|---|---|
| AC-1, AC-6 | integration (Temporal test server) | Lifecycle, pause, resume without burst |
| AC-2, AC-3, AC-4, AC-5 | unit and integration | Each policy's decision table, caps, batching, the gate, Advise drafts |
| AC-7, AC-8 | unit | Feed rows; delegation refusals |
| AC-9, AC-10 | unit and vitest | Due dates; screens and states |

## 19. Rollout
- Behind a feature flag per firm, on in local first.
- Existing engagements start with no due dates, so no reminders fire until someone sets one.

## 20. Open questions
All resolved: the founder approved every recommendation below on 2026-10-10.
- **Q1. Whose authority does the agent act under?** *Recommendation: the engagement's earliest-added active partner, as the `AgentContext` initiator,* so walls, independence and the matrix apply as for a person (ADR-025). The alternative, a system run, would bypass the per-person checks.
- **Q2. Due dates: per item with a request-list default?** *Recommendation: yes.* It's the smallest model that supports reminders; fieldwork dates and milestones come with the planner.
- **Q3. Reminder cadence and time zone?** *Recommendation:*
  - the first reminder on the business day after the due date, then every 3 business days, at most 3 per item;
  - sent at 9:00 in the firm's time zone, skipping weekends;
  - firms have no time zone yet, so add one (default US Eastern), set on the Autonomy page.
- **Q4. Routine sends automatically and Advise drafts?** *Recommendation: yes,* matching ADR-061 ("routine reminders" at level 1).
- **Q5. Model `firm_setting(autonomy_policy)` in `authorise` for `follow_up.send` (an `identity/authz` change)?** *Recommendation: yes.* It's the matrix's existing intent. The alternative is checking autonomy in the service, which AUTHZ-001 forbids.
- **Q6. The team digest: daily in-app to the partner and managers?** *Recommendation: yes;* no staff email in v1.
- **Q7. Start agents for existing non-archived engagements?** *Recommendation: yes, once.* With no due dates set they only screen, retrieve and match, as today.
- **Q8. Does the pause also stop the platform's rule-based retrieval and suggestions on that engagement?** *Recommendation: yes.* "Paused" should mean nothing automatic happens there.
- **Q9. Who pauses?** *Recommendation:* the engagement partner and managers for their engagement; firm administrators for the whole firm, with fresh MFA.

## 21. Future / explicitly deferred
- **The planner:** a daily model-proposed plan on code-computed state, validated against autonomy and the matrix (ADR-060), with its evaluation suite.
- The narrative daily briefing (ADR-063), the command bar, the Manage and Portfolio levels.
- Specialists as child workflows (chaser, support finder, change analyst), and autonomy per engagement.
