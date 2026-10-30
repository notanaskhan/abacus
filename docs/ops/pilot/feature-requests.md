# Partner feature requests: triage and written answers (F-09-T128)

Every capability a design partner asks for (in a session, a retro, the shared inbox) is triaged
against the scope decisions **D1–D10** and the exclusions **X-01…X-08** (the Scope Decision Record,
DEC-19) and answered **in writing**. Acceptance: every request has a written answer naming the epic,
the deferral or the exclusion. `python -m abacus_tools.quality.feature_requests` (check-fast) refuses
a row that does not.

**Rules.** Pilot codes only (no firm or person names); a request is described without client data. A request is never promised
in a session: it is logged here, triaged, and answered. A defect is not a request: it goes to the
top-10 log (`docs/ops/pilot/pilot-0-usability-log.md`).

## How to classify

| Verdict | When | The answer names |
|---|---|---|
| `epic` | inside D1–D10 and on the plan: an epic owns it (now or in a later sprint) | the epic (e.g. `R-01`) and, when known, its sprint |
| `deferred` | inside scope but cut or not yet planned (an epic's cut list, a revisit) | the deferral: the epic's cut list, or D10 (governmental audit, deferred) |
| `excluded` | an excluded area or a scope rule says no | the exclusion: `X-01`…`X-08`, or the rule (D4 no new top-nav items; D6 benchmarks only through an opt-in network; D7 one Accrued Agent, no named personas; D8 licensed methodology content is a business decision) |

Quick reference (titles from the Scope Decision Record): D1 SOC 1 and SOC 2 (and AUP) a service
line · D2 co-sourced internal audit · D3 the Sheets engine is hybrid · D4 no new top-nav items · D5
time capture stays integrate-first · D6 peer benchmarks only through an opt-in network · D7 one Accrued
Agent, no named personas · D8 licensed methodology content is a business decision · D9 eight areas out
of scope · D10 governmental audit (Yellow Book, Single Audit, fund accounting) deferred · X-01 banking
regulation · X-02 ESG assurance · X-03 forensics and litigation · X-04 federal environment · X-05
AIUC-1 · X-06 government fund accounting · X-07 PCAOB issuer audits · X-08 corporate in-house
workspace.

## Log

| # | Received | Pilot | Request | Verdict | Names | Answered on | Answer (vault) |
|---|---|---|---|---|---|---|---|

_No request yet: Pilot 0 has not run (Jan 11 – May 28, 2027). Recorded 2026-10-30._
