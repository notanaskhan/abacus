# CLS-11 · Ledger console · Copperleaf QuickBooks Online

| Field | Value |
|---|---|
| Route and params | `/clients/$clientId/entities/$entityId/ledger` (C-02 §5.1) in the Closes area behind `closes.gl_console`; search `close` (the back chip's close), `log=events` (a2), `reconnect=1` (d2) |
| Template and host frame | T1 variant (subbar · filter bar · status tiles · connection pane 420 + log pane flex) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLS-11 GL sync console - Copperleaf - QuickBooks Online/` |
| Epic and tasks | C-02 · SPEC-700, SPEC-701; screen contracts and scenarios C-02-T15 (TASK-8624); screen and live swap per `docs/plan/epics/C-02.tasks.csv` |
| Manifest status | live (C-02-T35: a, a2, c, d, d2; C-02-T44: b, b2, e) |

Parity tier target: C (C-02 §5.5). Copy keys live in `apps/web/src/screens/CLS-11/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written: `cas_delivery_slice.cls11_console()` writes `apps/web/src/fixtures/seed/scenario.cls11-console.json`.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Connected | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon Sep 14, 9:24 AM | live | AY |
| a2 | Sync events | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | live | AY |
| b | Posted | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 10:22 AM | live | AY |
| b2 | Batch drawer | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | live | AY |
| c | Needs attention | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 10:03 AM | live | AY |
| d | Needs reauth | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 9:14 AM | live | AY |
| d2 | Request reconnect | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | live | AY |
| e | Closing date conflict | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 10:21 AM | live | AY |

## Deviations
- Personas and clocks per state are in the scenario file (CLS-07 c, c2, d are Priya Raman's; the README's viewer column names Raj).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens CLS-02 · August 2026 close | CLS-02 | designed (handoff link graph) |
| Opens WB-11 · QuickBooks Online integration detail | WB-11 | designed (handoff link graph) |

## Design deltas (C-02-T10, DEC-5509)
Each row is the frame it amends (an annotated handoff screenshot) and the build answer; none needs a backend change outside the C-02 backlog.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `screenshots/CLS-11a.png` Write scope row | "Journal entries · recategorizations · attachments" | "Journal entries · closing date" | W1 v1 writes only JEs and the closing date (ADR-344 §1; SPEC-700 Q2) |
| `CLS-11a.png` Authorized by | Mar 9, 2026 | Mar 9, 2026 is the write grant; the connection is Mar 4, 2026 (POR-16e) | seed contradiction settled (DEC-5508) |

## Data and states (C-02-T35, DEC-5924)

| Letter | Data condition | Reads |
|---|---|---|
| a | `connection.health = connected`, grant `granted`; tiles 7 posted batches, 1 proposed, 0 open failures, closing date Jul 31 | `GET …/ledger-console`, `GET …/posting-batches`, `GET …/ledger-pull` |
| a2 | a's data on the Sync events segment (`?log=events`) | `GET …/ledger-activity` (finished runs on readable engagements, posts, failed attempts, closing dates) |
| c | `health = needs_attention`, `status_reason = rate_limited`, `last_failed_at` 10:02 AM, `retry_at` 10:07 AM | as a; Retry now is `POST …/ledger-pull` |
| d | `health = needs_reauth`, `status_reason = token_expired`, `last_failed_at` 9:02 AM; banner and posting paused; Sync now off | as a |
| d2 | d's data with the confirm open (`?reconnect=1`): the POR-20 email for the owners before sending | `GET /v1/connections/{id}/reconnect-requests/preview`; Send request is `POST …/reconnect-requests` (A-02-T23) |

Writes: Sync now (`ledger.pull`, C-01-T17), Request reconnect (`connection.reconnect_request`), Export (`ledger_connection.export`, the posting-log CSV). No credential field anywhere; reconnecting is the owner's step in POR-16.

## Links (wired)

| From | To | How |
|---|---|---|
| Back chip "‹ August 2026 Close" | CLS-02 | `to.CLS02({ closeId })` |
| Integration details › | WB-11 | `ov.WB11("quickbooks_online")` |
| CLS-07d "View in ledger sync ›" | CLS-11 | the close route's `onLedgerSync` (close's client and entity) |

## Deviations (C-02-T35)

- The tiles count batches (DEC-5924); C-02-T20 counted entries.
- The reconnect confirm names the owner ("Reconnects in", "Tess signs in … never sees or enters the client's ledger password"), not "She"/"her": the owner varies by client.
- The confirm also shows the email preview (row acceptance: "Request reconnect shows the POR-20 preview before sending"); the handoff's dialog shows only To, Sends and She reconnects in.
- Not shown, no C20 field: "(Aug 1–31)" after the read count, the Bank feeds row, and the two "… are in the export" notes in a2 (the export is the posting log only). Agents using it shows only when the read names dependents.
- Day headings use the kit's `weekdayDate` ("Today · Monday, September 14") rather than "TODAY · MON SEP 14".
- The failure's resolution reads "resolved: retried by Raj Malhotra, 2:41 PM"; the handoff's "account reactivated by" is a narrative the data does not hold.
- Parity diffs per artboard are recorded when the e2e walk runs in the end pass (`e2e/screens/CLS-11.spec.ts`).


## b, b2 and e (C-02-T44, DEC-6029)

| State | Data condition | Reads |
|---|---|---|
| b | 2026-08-A `posted` at 10:20 AM (QBO 48213–48218, $35,300.00); tiles 8 posted · 0 proposed; closing date Aug 31 set by Raj Malhotra at 10:22 AM (same day: the time only) | as a |
| b2 | b's data with `?batch=<2026-08-A>`: the O2 drawer with Status, Amount, Posted, QuickBooks ids and the six entries, each QBO id an `<a target="_blank" rel="noopener noreferrer">` to the server's `deep_link`; footer "Open in Adjustments (CLS-07)" | `GET /v1/posting-batches/{id}` (additive `entries[]`: ref, description, amount, `external_txn_ref`, `deep_link`) |
| e | 2026-08-A approved (6 of 6) and held: the console's additive `conflicts[]` lists its six entries dated Aug 31 against the Aug 31 closing date, which the pane shows as "changed in QuickBooks Online · found by the 10:02 AM sync" (`closing_date_set_by` null) | `GET …/ledger-console` |

Writes (e): "Ask the client to lift the date…" posts C8's `ask-client` for each held entry; "Re-date to Sep 1…" posts `redate` with a reason for each. Both are a person's clicks in a confirm dialog.

**Deviations (C-02-T44).** (1) The handoff draws one conflict row per batch; the database keeps one conflict per entry (0950), so the band groups entries by batch and date ("6 approved entries dated Aug 31") and its actions act on each. (2) The ask and re-date dialogs' body copy is ours: the handoff names only the two actions. (3) `deep_link` is built server-side from QuickBooks' numeric id and the deployment's QBO environment; a non-numeric reference gets no link (client-system text, ADR-052). (4) The seed's August posting time is 10:20 AM, as the handoff's row and drawer read; the closing date moved at 10:22 AM.
