---
id: RB-68
title: "OCR December enablement: soak, x100 load profile, daily page caps, alarms, kill-switch drill, per-firm flip"
owner: builder
alarms: [abacus-staging-textract-request-rate, abacus-staging-ocr-daily-cap-80, abacus-staging-textract-throttled]
last_rehearsed: never
rehearse_by: 2027-12-17
---
# RB-68 · OCR December enablement

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 (a firm hits its cap: `quota_exceeded` refusals, manual entry) to SEV2 (Textract throttled across firms) |
| Source | P-11-T33; P-11 §cost, AC7.2, R9, OQ-10; DEC-2715 |

Everything here runs before the Jan 1, 2028 window. Rows that need staging or production (the soak,
the drills, the flips) are ops; their firm half runs on PF-X1 (Brightwater Hale, DEC-1530) and is
reported as synthetic.

## 1. The x100 load profile (what the drive must reach)
`python -m abacus_tools.loadtest.ocr_capacity --firms <N>` prints the peak-hour pages per minute,
DetectDocumentText and AnalyzeDocument (FORMS) TPS against 80% of quota, the pages the cap refuses
per firm, and the worst-case time for a 20-page upload (pages are read one after another). It exits
1 when a quota or the 3-minute target fails. Its inputs marked "inferred" are planning assumptions,
replaced with the soak's numbers:

| Input | Default | Why |
|---|---|---|
| Baseline pages per firm a day | 50 | the PF-X1 rehearsal day; x100 = 5,000, the default cap |
| Peak-hour share | 20% | a fifth of the day's pages in its busiest hour |
| FORMS share | 30% | pages naming a TIN go on to AnalyzeDocument FORMS |
| Cache hit share | 0% | the page-hash cache, cautious case |
| DetectDocumentText / AnalyzeDocument quota | 10 / 10 TPS | confirm in Service Quotas (us-east-2); raise through `textract_quota_requests` |
| Call p95 (detect / FORMS / rasterise) | 2.0 / 4.0 / 0.5 s | replace with the soak's OTel figures |

At the defaults the DetectDocumentText headroom carries 28 firms at their caps. Above that, request
the quota (a reviewed `textract_quota_requests` change) before the load test, not during it.

The read side runs as `python -m abacus_tools.loadtest.run --profile ocr_december` on the perf
stack beside the page drive (scanned uploads through the scanner and Textract fakes); the "p95 3
minutes for 20 pages" figure is the `upload.ocr_read` span from upload to fields in OTel.

## 2. Staging soak
1. `textract_enabled = true` on staging only after P-11's provider-terms entry covers `textract`.
2. PF-X1 with `evidence.ocr` on; run the drive at the capacity plan's pages per minute for 2 hours.
3. Record: OCR p95 for 20 pages, throttles, refusals by reason, Textract cost for the run. Replace
   the inferred inputs above with these numbers and re-run the plan.

## 3. Daily page caps
- Default 5,000 pages per firm per day (OQ-10); the gate refuses past it with `quota_exceeded`
  (a refusal, never a queue; manual entry is offered).
- A firm's own cap is the latest `ocr_daily_caps` row (0714). Set it with the ops command, as an ECS
  one-off task, never from a laptop against a shared database:
  `python -m abacus_tools.ocr_daily_cap <tenant> <pages> --raised-by <op> [--second-by <op>] --reason "..."`;
  `--show` prints the current cap.
- Above 5,000 needs both founders (R9): the table refuses a raise without a second, different
  operator. Lowering needs one. Rows are never changed; a new row replaces the cap.

## 4. Alarms
| Alarm | Fires when | First move |
|---|---|---|
| `textract-request-rate` | successful calls above 80% of the DetectDocumentText quota for 3 minutes | check the capacity plan; file the quota request; nothing is rerouted |
| `ocr-daily-cap-80` | a firm's read crossed 80% of its cap (the worker's `ocr.daily_cap_warning` line: tenant id and counts only) | tell the firm admin; raise only with both founders |
| `textract-throttled`, `-usererrorcount`, `-servererrorcount` | as RB-47 | RB-47 |
| Textract budget | forecast above 80% of the month | RB-47 |

## 5. Drill (staging, PF-X1)
1. **Cap:** set PF-X1's cap to 25 (`--reason "RB-68 drill"`), upload a 30-page scan: 25 pages read,
   the alarm fires at 20, the rest refused `quota_exceeded`, SHL-08 shows the refusal line. Set it
   back to 5,000.
2. **Kill switch:** turn on `model_route_block` for route `textract`; the next scan is refused
   `kill_switch` before any call, no `ocr_runs` row has page units. Turn it off.
3. **Alarms:** confirm both new alarms reached the alarm topic. Record the drill in this file's
   `last_rehearsed`.

## 6. Flag renewals (Dec 14-18 bundle)
P-11's flags: `evidence.ocr` and `evidence.form_extraction` (expire 2027-05-01) and
`reporting.generated_documents` (2027-04-21). A renewal runs at most 180 days from its own day
(DEC-137), so each is renewed in turn until the Dec 14-18, 2027 bundle, where a renewal dated
Dec 14 runs to Jun 11, 2028: no P-11 flag expires inside Jan 1 to Apr 20, 2028. The 2027 renewals
cannot be written in 2026; this section is the checklist for them.

## 7. Per-firm flip checklist
For each firm, in order, before turning `evidence.ocr` on:
1. Provider-terms entry covers `textract` today, and the firm's boundary basis is recorded (the
   AI-services opt-out evidence, or a synthetic firm).
2. §7216: the firm's TRI scopes have C19 consents, or counsel's `tri_basis` is on the entry.
3. The firm's cap is right (`--show`); a raise has both founders on its row.
4. Turn on `evidence.ocr`; run `python -m abacus_tools.ocr_backfill <tenant>` (ECS one-off task) for
   the firm's `not_scannable` pages.
5. Watch the first day's refusals by reason and the 80% alarm. Rollback: turn the flag off; pages
   go back to `not_scannable` with manual entry, nothing already read is removed.
