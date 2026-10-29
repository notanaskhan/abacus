# Pilot operating model and the support desk

Q-04-T014 (Q-04 §3.7, group G; SPEC-402). How Accrued runs a pilot from the first shadow window
(PW1, Tue Jun 1, 2027, M9) to GA: who owns what, how a firm reaches us, how fast we answer, and
what a ticket may hold. Rotas per window live in `docs/ops/on-call.md` (Q-04-T020); incident steps
in `docs/runbooks/` and `docs/ops/incident-templates.md`.

**Firm names never enter git.** Every pilot firm is a **pilot code**: PF-A1…A3 (audit and EBP),
PF-T1 (tax), PF-C1 (CAS), then cohort codes. The code-to-name map lives only in the founders'
vault (F-09 keeps it). Tickets, docs, commits and metrics use the code.

## Owners

| Role | Who | Owns |
|---|---|---|
| Partner-facing owner | AY (ayushkbhatia) | The shared inbox, first responses, office hours, SEV3 triage and filing, window and flip notices, retros, onboarding content |
| SEV1/2 on-call, primary | N (notanaskhan) | Paging, incident command, rollback, flips of N-owned flags, the hotfix lane |
| SEV1/2 on-call, named backup | Named per window in `docs/ops/on-call.md` (AY by default in PW1) | Takes the page when the primary has not acknowledged within 15 minutes; a SEV1 pages both |

Severity is ADR-097's: **SEV1** suspected cross-firm exposure or a full outage in busy season;
**SEV2** a major feature or provider outage; **SEV3** degraded service or one firm.

## Service levels

These are the founding-partner agreement's terms; a change to either is a change to the
agreement first, then here, word for word.

| Kind | Target |
|---|---|
| Partner request to the shared inbox, in season | First response within **2 business hours** |
| Partner request, out of season | First response within 1 business day |
| SEV1 | **24x7**: acknowledged within 15 minutes (else the backup is paged); status page updated within 30 minutes; a firm whose data an Accrued-originated incident touched hears from us within 72 hours, with an ADM-06 register entry (RB-27) |
| SEV2 | Acknowledged within 15 minutes inside a live window's working hours, otherwise by the next business morning |
| SEV3 | Filed on the owning epic within 1 business day |
| Postmortem (SEV1, SEV2) | Blameless, within 5 business days; its action lands as a test, rule, alert or ADR (ADR-097) |

Business hours: Mon–Fri, 8:00 AM–6:00 PM CT. "In season" is any live window in
`docs/ops/release-windows.md` (Q-04-T001).

## The shared inbox

One shared inbox for all pilot firms, owned by AY. Every ticket carries three labels and nothing
that identifies a client:

| Label | Values | Example |
|---|---|---|
| Screen | The screen ID the request is about | `AUD-03`, `POR-04`, `TAX-02` |
| Pilot | The pilot code | `PF-A1` |
| Severity | `SEV1`, `SEV2`, `SEV3`, `question` | `SEV3` |

**No client data in tickets.** No client or person name, no amount, no TIN or account number, no
file, no screenshot of client data. Describe the state ("request row stays Requested after upload
on POR-04"), not the content. Anything the investigation needs is read in the product, under a
support session the firm approves (DEC-72: in ADM-06, one work item or return, at most 2 hours,
US-located staff only until counsel answers D-OPS-21). A ticket that arrives with client data is
redacted on receipt and the sender is reminded once.

## Office hours

Tue and Thu, 11:00 AM–12:00 PM CT, during every live window: AY hosts, N joins for the first
week of each window and for any open SEV2. Agenda: open tickets for the firm's pilot code, the next
flip, and the firm's W-signals.

## Signals and thresholds

The pilot signals are read from code, never estimated: thresholds are in
`docs/product/discovery/thresholds.md` (W1–W8; W9 paid conversion and W10 tax pilot are set before
their windows open), and W4–W7 are computed weekly per firm by `PilotMetricsWorkflow`
(Q-04-T008). Retros (M10, M12, M14 and each season) read the same snapshots.

RK-07 fires when support hours exceed the sprint's reserve rows two sprints running, the SEV3
backlog exceeds 5, or the first-response target is missed twice in a month: onboarding of the next
firm pauses and the next cut tier is invoked (never the hardening reserve).

## Check before PW1

- [ ] The SLA table above matches the signed founding-partner agreement word for word (AY).
- [ ] A test request to the shared inbox is labelled (screen, pilot code, severity), answered
      inside 2 business hours, and holds no client data.
- [ ] `docs/ops/on-call.md` names the backup for every PW1 day (Q-04-T020).
- [ ] Every PW1 firm admin has acknowledged `shadow-briefing.md` (current version) in writing (Q-04-T022).
