# N-04 hand-off notes (N-04-T27, 2026-11-07)

What each later epic can rely on from Notices v1 (frozen: `docs/contracts/notices.md`, snapshot
`backend/tests/contracts/notices/v1.json`), and what it still has to add. Each seam below is read
through `abacus.modules.notices.api` only; no epic queries the notices tables.

## W-03 (library card #17, "Notice Intake & Response Drafter")
- **Ready:** the capability `notices.responder` v1, spec `backend/src/abacus/modules/agents/specs/notices.responder.yaml`, modes `analyze` and `extract`, its suite `evals/notices_responder` and the real-run harness (`--route direct|bedrock`, N-04-T25).
- **Not ready:** clearance. `evals/notices_responder/clearance.yaml` is empty; `analyze` waits on the CPA label review (`label_review: pending`) and both modes on a signed Bedrock run. The card must say so until `client_data` reads `cleared`.
- **The rule the card states:** live per firm only after 28 days of shadow, 10 compared notices and no amount disagreement, on top of SPEC-036 (`docs/ops/pilot/notices-responder-shadow-plan.md`).

## T-08 (HOME-03, S53)
- **Ready:** open notices per client (`organisations.register_open_notices`, CLI-05's band) and the HOME-01 deadline rows (`DeadlineRowOut.kind = notice`).
- **To add:** `notice_facts` in `notices.api` (the plan's name), read by HOME-03 when T-08 lands. Nothing calls it yet, so it isn't built ahead of its consumer.

## R-03 (POR-19 mobile capture, payments)
- **Ready:** a client's payment confirmation reaches them through the binder request sent at mark-sent (DEC-2386); POR-03's "Upload something else" files into NOT-01's intake through the inbox destination.
- **To add:** `payment_facts_for` in `notices.api` for R-03's payment screens, and the QR hand-off from POR-19 into a notice intake. The confirmation names IRS Direct Pay in words, without a link, until firm content carries one (DEC-2386).

## N-03 (citations)
- **Ready:** every analysis paragraph cites lines of the notice's evidence (C4), and the response's cited lines are its blocks' sources.
- **To add:** `notice_state_for_citation` in `notices.api`, so a citation viewer can say "this notice is closed" or "superseded" beside a quote.

## Open at hand-off
- Real pilot firms: none (DEC-1391). PF-X1 (synthetic) carries the Whitley CP2000.
- Pen test #2's notices findings: deferred with every penetration test (DEC-1389).
- Flag retirement: `notices.workspace` and `notices.responder` retire in their own PR, held for the Thu Dec 16 batch (DEC-2602).
