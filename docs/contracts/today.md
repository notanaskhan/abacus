# Today (the brief's read model and routes)

- **Status:** stub (I-02-T03, TASK-7612, 2026-11-12; DEC-4609). Live at I-02-T10, T13, T14, T16.
- **Provider:** `practice` (`practice/today/`: the read model and five routes; amber) and
  `workbench` (the questions route shape; the turn runs on `agents`' session workflow v2, red).
  Briefing rows and their verified prose: `agents` (`daily_briefings`, I-02-T06 to T13).
  **Spec:** SPEC-654. **Epic:** I-02 §4.3, §8.2.
- **Callers:** SHL-23 (the panel, docked or the `?ov=today` drawer), HOME-05 (Home docked), HOME-01
  ("Open Today ›", the bell entry). Not the portal: client roles hold none of the actions.
- **Flag:** `today_brief.enabled` (off: 404 everywhere, no panel, no link, HOME-01 unchanged).
  The questions route also needs `workbench.enabled`.

## Routes
Each answers, in order: the matrix (403), `today_brief.enabled` (404), then 501 until its row.
Every route reads only the caller's own brief (`viewer_user_id = caller`).

| Method · path | Action | Shape | Served by |
|---|---|---|---|
| `GET /v1/me/today?date=` | `briefing.read` | `TodayVM` | I-02-T10 |
| `POST /v1/me/today/builds` `{brief_date, mode: missing\|force\|background}` (`background`: the stale engagements only, debounced 15 minutes and six a day; TASK-7930) | `briefing.rebuild` | 202 `TodayBuildAcceptedOut`; 429 `rebuild_limit` (a fourth forced rebuild a day); 409 `in_progress` | I-02-T13 |
| `GET /v1/me/today/work-items/{work_item_id}?date=` | `briefing.read` (+ `visible(work_item)`) | `DrillVM`; 404 walled or not the viewer's | I-02-T10 |
| `GET /v1/me/today/history?before=&limit=` | `briefing.read` | `HistoryPage` (90 days) | I-02-T16 |
| `GET /v1/me/today/history/{brief_id}` | `briefing.read` | `TodayVM` (read-only, walls re-checked, citations re-verified) | I-02-T16 |
| `POST /v1/me/today/questions` `{text, brief_id}` | `briefing.ask` | 202 `TodayQuestionAcceptedOut`; 409 `capability_unavailable {reason}`; 422 `text_too_long` (> 1,000) | I-02-T14 |

## Models (every field classified)
- `TodayVM`: `brief_date`, `brief_id`, `first_name`, `items`, `engagements` ("11 items across 4
  engagements"), `cells[CountCell]`, `lead_facts[LeadFact]`, `layout` (`focus`, `by_engagement`),
  `needs_you_first[GateRow]`, `cards[Card]`, `groups[Group]`, `availability`, `status`
  (`building`, `ready`), `needs_build`, `built_at`, `building_counts`, `stale_engagements` (ready
  briefs naming a gate closed since; the panel says "Written … · items changed since" and asks
  for a background rebuild; TASK-7930).
- `CountCell {kind, count, href}`: kinds are C13's bands in HOME-02 order (`decision`, `sign_off`,
  `approval_send`, `signature`, `needs_attention`) plus the derived `overdue`.
- `LeadFact {key, values, refs}`: keys `lead.overdue` › `lead.due_tomorrow` ›
  `lead.blocked_signoffs` › `lead.decisions_blocking` › `lead.signatures_week`; values are
  integers, dates and C13 short labels. The frontend renders at most two sentences from them
  (`screens/SHL-23/copy.ts`).
- `GateRow {gate_id, kind, title, due {due_on, days, tone}, state, deep_link, context_line,
  why_blocks, folded, highlight_refs}`; `Card {engagement_id, work_item_id, label, rows, more,
  briefing_id, briefing_status, unavailable_reason, summary_blocks}`; `Group {key, count, summary,
  href, items[GroupItem]}`; `DrillVM {work_item_id, title, summary_blocks, summary_fallback,
  blockers, downstream, prefills[AssignPrefill], not_assignable, open_href, select_refs}`;
  `HistoryRow {brief_id, brief_date, built_at, counts}`.

## Rules the provider keeps
1. **I-COUNT.** Every count (cells, groups, `items`, lead-fact integers) is computed by the same
   `practice` home service over `human_gates` as HOME-01 and HOME-02, in the same request. No
   field is fed by `daily_briefings.blocks` (the T05 contract test holds the schema to it).
2. **Model prose is verified blocks.** `why_blocks`, `summary_blocks` and `detail_blocks` are
   `AgentBlocks` v1 `p` parts by reference into the run's fact registry; an `unverified`,
   `failed` or `unavailable` briefing leaves them empty and the row shows its code `context_line`
   (INV-2). The model never claims an approval, signature, decision, assignment or send (INV-1).
3. **Walls** (DEC-43): a walled engagement is absent from every cell, card, group, drill-in and
   history row; nothing counts what was left out.
4. **Deep links are C13's**; the brief hardcodes no target.
5. **Assign open items** returns prefills only; the person presses Create in SHL-17 (P-05's
   `POST /v1/todos`, `todo.created` with the person as actor). Items reserved to the viewer are
   `not_assignable: reserved_to_you`; the agent is never an assignee (INV-1, INV-5).
6. **Questions** run read-only: `propose` and `approved_write` tools are withheld whatever
   `workbench.plans` says.

## Status words (C2)
`daily_briefing` (Building, Ready, Unverified, Failed, Unavailable; panel and footer context
labels); `attention_item` (Letter unsigned, Missing support, {n} requests open), all I-02-T03.

## Human-only actions
Decisions, sign-offs, approvals and sends stay on their own screens (SHL-11, SHL-12, HOME-02);
to-dos are created by the person (SHL-17). No agent, system, support or client principal holds a
`briefing.*` action (I-02-T04).

## Audit events
`today_brief.question_asked` (no content, DEC-60); `daily_briefing.built` (identifier-only
invalidation on `user:{me}`); builds and forced rebuilds are audited by `agents` (I-02-T13).

## Fixtures
`apps/web/src/fixtures/seed/today.ts` (SHL-23 1–7, HOME-05 a–f: Daniel, the Ridgeline drill-in, a
question accepted, Margaret, Margaret on Dec 1, quiet, building, `by_engagement`) through
`fixtures/handlers/today.ts` in the E0 scenario. Consumer tests: I-02-T05.
