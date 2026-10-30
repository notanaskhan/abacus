---
id: RB-16
title: Busy-season readiness
owner: builder
owning_epic: Q-04
alarms: []
last_rehearsed: never
rehearse_by: 2027-08-02
---
# RB-16 · Busy-season readiness

| Field | Value |
|---|---|
| Owner | builder (written by Q-04: Q-04-T055 the operator half; Q-04-T056 adds the partner-facing section) |
| Severity range | n/a: a readiness procedure, run before each window; a failure found here is a SEV3 on the owning epic, or a SEV2 when it would break a live path inside the window |
| Linked from | the R4 dossier (`docs/ops/go-live/<pilot-code>.md`, Operations, `operations-5`), `make go-live-check LEVEL=season` (`season.runbooks_rehearsed`), `docs/ops/release-windows.md` |
| SLO affected | all, for the window it protects |
| Kill switches that apply | none of its own; the window's incidents use RB-01, RB-03, RB-18, RB-19, RB-20 and their switches |
| Rehearse by | Aug 2027 (the staging walk-through is Q-04-T057, with RB-18 and RB-19, before Tue Aug 31, 2027) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

What this protects: a firm's busiest weeks. ADR P-29 (DEC-68) sets the windows and
`docs/ops/release-windows.md` is the rule; ADR-075 sets the yearly readiness programme. This runbook
is the procedure that turns both into a dated, signed checklist before each window, and the rules
both founders follow inside it. Owners: **N** is notanaskhan, **AY** is ayushkbhatia (`docs/ops/pilot/README.md`).
Firms appear only as pilot codes. Contacts, account ids and quota case numbers live in the vault (`V-…`).

## 1. Recognise it

Run this runbook when any of these is true:

- **An R4 review is due.** R4 is the season-ready gate before each window: Tue Aug 31, 2027 (autumn
  2027, tax and EBP firms), Fri Dec 10, 2027 (season 2028, with the ADR-075 load test), Fri Aug 25,
  2028 and Fri Dec 8, 2028 (Q-04 AC-10.1). Start **six weeks** before the R4 date: provider quota
  increases take days to weeks.
- **A firm goes live inside the next 60 days** on work a window covers (tax or EBP for autumn,
  anything for the season window): its first real data starts its windows (P-29).
- **`make go-live-check LEVEL=season` is red** for any live firm, or `season.runbooks_rehearsed`
  names RB-16, RB-18 or RB-19 as never rehearsed this quarter (AC-10.3).
- **`make flag-calendar` shows a flag expiring inside the coming window**, or `make check-fast`
  refuses `deploy/windows.yaml` (a missing entry, an overlapping window, a firm without its code).

## 2. Contain

Readiness gaps are contained by keeping change away from the window, not by fixing in it:

1. **Freeze the scope of the coming window** (N). Anything that will not be green by the R4 date is
   moved dark until after the window ends (Oct 20 or Apr 20): its flag stays off for live firms and
   its rows go to the post-window train. Record each move in the R4 dossier's Operations notes.
2. **Renew, never extend into the window** (N). A flag whose expiry falls inside the window is renewed
   now as a registry-only change (`release-windows.md` §2), with the renewal date after the window.
3. **No new firm goes live in the two weeks before a window opens** unless both founders sign its
   dossier at `LEVEL=season` as well as its own level (AY records the decision).

## 3. Preserve

Keep the evidence the R4 review signs:

- `make go-live-check FIRM=<tenant_id> LEVEL=season` output per live firm, filled into the dossier
  with `python -m abacus_tools.go_live_dossier fill <pilot-code> --report <file>` (N).
- The provider quota requests: provider, limit asked, limit granted, date, vault reference (N).
- The rehearsal log rows of RB-16, RB-18 and RB-19 (below; each runbook's own log) (N, AY).
- The window notice as sent and each firm's acknowledgement date (vault reference only) (AY).
- The load-test result where the gate needs one (`docs/ops/loadtests/`; Q-03 owns the run) (N).

## 4. Assess

### The R4 checklist

Work it top to bottom. Each step has one owner; the other founder checks it at the review. A step is
done when its evidence is in the R4 dossier, not when it is believed done.

| # | Step | Owner | Evidence | Due |
|---|---|---|---|---|
| R4-1 | `deploy/windows.yaml` has the coming window's entries for every live firm it covers (pilot code, window, mini-freezes, deadline weeks), and `make windows YEAR=<y>` prints the dates in `release-windows.md` §6, re-checked against C21's due-date reference set (IRC §7503 shifts) | N | `make windows` output; the C21 reference-set version | R4 − 21 days |
| R4-2 | `make go-live-check LEVEL=season` green per live firm: no flag expiring inside the window, season runbooks rehearsed, windows entries present | N | the filled dossier section | R4 − 7 days |
| R4-3 | Flags renewed past the window end (registry-only), owners named, `make flag-calendar` clean through the window | N | `make flag-calendar` output | R4 − 14 days |
| R4-4 | Reference sets current for the season (C21: due dates, form sets, Pub 1345 tolerances), published and pinned per firm | N | reference-set versions per firm | R4 − 14 days |
| R4-5 | **Provider rate-limit requests** filed and granted (§4, below) | N | the quota table in the vault, referenced by `V-…` | R4 − 7 days (file at R4 − 42 days) |
| R4-6 | Extended on-call published in `docs/ops/on-call.md` for every window day: a primary and a different named backup; quiet hours suspended in deadline weeks; deadline-week double cover (Q-04-T066); a test page escalates primary → backup within 15 minutes | N | the rota PR; the test page's timestamps | R4 − 7 days |
| R4-7 | RB-18 (e-signature or KBA provider outage, record mode) and RB-19 (tax-engine bridge failure, file fallback) rehearsed on staging with both founders this quarter; RB-16 walked through end to end | N, AY | each runbook's rehearsal log row | R4 − 7 days |
| R4-8 | Restore drill (RB-10/RB-15) and game day held inside the quarter | N | the drill record | R4 − 7 days |
| R4-9 | Load test where the gate needs one: the ADR-075 December peak test before a season window (x100), the tax-surge profile before autumn (Q-03-T131) | N | the result file with its pass/fail thresholds | R4 − 7 days |
| R4-10 | SES: every live firm's sender domain verified (DKIM, custom MAIL FROM); bounce and complaint rates under RB-20's thresholds; sending quota covers the window's peak (§4) | N | ADM-10 state per firm; SES quota | R4 − 7 days |
| R4-11 | The window notice (partner section, below) sent to every live firm's champion and admin, and acknowledged | AY | acknowledgement dates (vault) | R4 |
| R4-12 | Support desk ready: office-hours calendar for the window, deadline-week extended hours, the shared-inbox labels and first-response targets confirmed against the founding-partner agreement | AY | the calendar; `docs/ops/pilot/README.md` check rows | R4 − 7 days |
| R4-13 | The deadline-week plan: each deadline week's watch rows assigned (Q-04-T071, T078, T085 for 2027), non-urgent work moved out of those weeks (RK-51) | N, AY | the sprint plan rows | R4 |
| R4-14 | Both founders sign the R4 dossier for each live firm | N, AY | the dossier's Sign-off table | R4 |

A step that cannot be green by the R4 date is not waived: its feature goes dark for the window
(§2 step 1) and the dossier says which.

### Provider rate-limit requests

Request every increase well before the window (ADR-075): limits found in a deadline week cannot be
raised in time. File at R4 − 42 days; chase at R4 − 21; the review reads the granted limits.

| Provider | What to request | How | Sizing |
|---|---|---|---|
| AWS Bedrock (US Geo profiles, pinned models) | Tokens and requests per minute for each pinned tier model | AWS Service Quotas, per model and region, from the production account | The window's peak from the last load test, x2 headroom; never reroute client data when throttled (RB-03) |
| AWS SES | Sending quota and maximum send rate | AWS Service Quotas / SES console | Peak notices and portal emails per hour in a deadline week, x2 |
| AWS KMS | Cryptographic operations per second in the home region | AWS Service Quotas | Decrypt p95 and throttles from the load test |
| E-signature provider (DocuSeal, ADR-342) | API request rate and envelope volume for the plan | Provider support case | 8879 envelopes per deadline week x2 (Q-03-T131's surge profile) |
| Ledger and mail connectors in use (Intuit, Microsoft Graph) | API throttling limits for the production apps | Each provider's developer console or support | Only for connectors a live firm uses in the window |

Record each request as provider, limit asked, limit granted, date and a vault reference. A request
not granted by the R4 date is a documented risk in the dossier, with the fallback named (record
mode for e-signature, queue and degrade for the model, RB-03).

## 5. Notify

- **Inside Accrued:** the R4 date, the checklist owners and every red step are posted in the sprint
  status file for the sprint that holds the R4 date (both).
- **To firms:** the window notice (the partner section, Q-04-T056) at R4 − 14 days at the latest, acknowledged by R4
  (AY). A change to a window, a mini-freeze or a deadline week after the notice is a new notice.
- **Inside the window:** every promotion and flip is announced to the affected firms the business day
  before the Tuesday slot, with what changes and that nothing changes in deadline weeks (AY).

## 6. Recover

The rules inside a window. They are `release-windows.md`'s; this is the operating procedure.

**The Tuesday 19:00 CT slot (N operates, AY approves).** The only promotion inside a window:

1. By Monday 17:00 CT: the release PR carries `window_mode` (`defect_only` or `dark_only`), its
   rollback link and, for each planned flip, the ops request with both approvals.
2. Tuesday before 15:00 CT: the staging journeys for every touched path green within the last 24
   hours; the shadow run clean; the canary green.
3. 19:00 CT: promote. The migrate step does not start before 20:00 CT and refuses contract
   operations inside a window (Q-03-T081's guard).
4. By 21:00 CT: production journeys and the canary re-checked; the release record closed with what
   ran. Any red check: roll back by the named rollback, then open the incident.
5. A week with no slot (a deadline week, or a mini-freeze that covers the Tuesday) has no promotion.

**Mini-freezes (both).** From the shifted extension deadline minus 7 days through the deadline (8
calendar days inclusive: 2027 Sep 8–15, Sep 23–30, Oct 8–15). No flip changes a live path; a
promotion still needs the Tuesday slot and is defect-only.

**Deadline weeks (both).** The Monday–Friday week containing a shifted deadline (2027: Sep 13–17,
Sep 27 – Oct 1, Oct 11–15). No promotion and no flip. Every day: the canary and SES deliverability
checked and logged, the providers' status pages watched, the primary and backup reachable (N); the
partner desk on extended hours (AY). Only the hotfix lane runs (production broken, a security fix,
or a founder asking now), and in a deadline week a hotfix needs both founders' approval in the
incident record.

**Extended on-call (N).** Every window day has a primary and a different named backup
(`docs/ops/on-call.md`; check-fast refuses a gap). In deadline weeks quiet hours are suspended and
both founders are reachable all day (double cover). SEV1 pages both at once, always.

## 7. Verify

- The R4 dossier for each live firm is green and signed by both founders before the window opens
  (Q-04-T063 for Sep 1, 2027).
- During the window: every release record shows `window_mode` and a rollback, every flip has both
  approvals, and each deadline week's watch row shows no release or flip and every daily check logged.
- After the window: the season retro reads the window's incidents, hotfixes and support hours against
  this runbook and changes it where it was wrong.

## 8. Review

At each season retro (Q-04-T087/T088 and their successors), in writing:

- Which R4 steps finished late, and why; move their due dates earlier next time.
- Which provider limits were hit or nearly hit; raise next year's request sizing.
- Every in-window hotfix: its reason, its recurrence test, and the layer that missed it (Q-03's
  escaped-defect rule).
- Whether the partner notice answered firms' questions; update the partner section, both approving.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
