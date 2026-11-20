---
id: RB-94
title: "Intuit meter budget exhausted (the hourly close sync)"
owner: builder
alarms: []  # the meter-budget alarm is C-01 §10 item 6, not built yet; the pause notice is the signal
last_rehearsed: never
rehearse_by: 2028-10-03
---
# RB-94 · Intuit meter budget exhausted

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 (scheduled syncs paused for one firm; Sync now works) to SEV2 (open closes past their due date on stale data) |
| Source | C-01-T56 (TASK-8758); C-01 R1 (Intuit metering, DEC-17, DEC-70); `connections/ledger_sync.py` rule 3; RB-04 hourly-sync addendum |

## What it is
Each firm has a monthly Intuit call budget per provider (`connection_meter_usage`: `calls`, `budget`, by month). When a scheduled tick finds `calls ≥ budget`, the entity's schedule pauses with `meter_budget_exhausted`, and the firm admin and the engagement's leads are told once per pause (`ledger_sync_paused`). Scheduled ticks skip a paused schedule. **Sync now** still runs (`POST /v1/client-entities/{eid}/ledger-pull`, a person's decision), and a Sync now that finds room clears the pause.

## Recognise it
- The ledger-pull status reads `paused` with meter `exhausted`; CLS-02 shows the stale sync time; the firm admin has the pause notice.
- Not this runbook: `needs_reauth` (RB-05), `rate_limited` (Intuit's throttle; it waits by itself), provider outage (RB-04).

## Contain
1. Nothing is lost: the closes keep their last snapshots (ADR-004) and say how old they are.
2. Tell the firm's close lead: Sync now on the accounts they are reconciling today, not on every entity. Each Sync now spends calls.
3. Do not turn the budget off or raise it without the firm's agreement and the plan's terms (the budget is the firm's cost guard; DEC-51 ties it to the order form).

## Recover
1. **Next month:** the meter starts a new month's row. Scheduled ticks still skip a schedule paused last month until a Sync now on that entity finds room and clears the pause; after the month turns, run one Sync now per paused entity (the close lead's call), or ask the firm to.
2. **Within the month, with the firm's agreement:** a raised budget is a reviewed platform change (there is no route that edits `budget` in v1); record the firm's written agreement and the new figure in the ticket, then run one Sync now per paused entity.
3. Verify: the ledger-pull status reads `synced`, freshness returns under 60 minutes, and the meter reads `ok` or `warning`.

## Review
Why the budget ran out: a catch-up after an outage (RB-04 addendum), many entities with unlocked old closes in scope (lock finished closes), or a budget set below the firm's entity count. Actions: lock or archive finished closes, adjust business hours, or agree a new budget.

## Rehearsal log
| Date | Where | Who | Result |
|---|---|---|---|
| — | staging | — | not yet rehearsed (needs the fake QBO with a small budget on a staging tenant) |
