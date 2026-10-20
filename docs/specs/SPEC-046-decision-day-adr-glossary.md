---
id: SPEC-046
title: "Decision register, ADR programme and glossary: the decisions, ADR numbers and words every later session depends on"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-133]
related_specs: []
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition: `docs/plan/AMENDMENT-solo.md` overrides any two-founder process in the epic. No owner, approver, test author, ruleset, reservation issue or merge window applies. Acceptance tests are written first from this spec; a test is never edited to make it pass.

## 1. Summary
This is epic F-02 (plan: `docs/plan/epics/F-02.md`) in its solo slice for setup and S0: one in-repo decision log (101 rows), one ADR backlog (69 proposals) as the only source of ADR numbers, the `AGENTS.md` stop-on-open-decision rule and product-naming decision, one glossary change set, a solo Decision Day session, and the M1 orphan ADR drafts (e-signature, write-capability framework, busy-season policy, clock and scenario). Guards, lint rules and tests (T07 to T12) are separate rows, covered later.

## 2. Problem and context
Every later epic depends on decisions made once and recorded in one place. Without the log and backlog a session can build against an open decision; without the glossary, sessions refuse legal Accrued words or invent synonyms; without the M1 drafts, F-04 and the vendor clocks stall. Setup step SU-12 creates T01 and T02 today, SU-08 delivered T03 (`AGENTS.md`, ADR-133), and Decision Day (T05) is a solo session under the amendment: no meetings, no approvals, plan's proposed option as default.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Builder | Decides, drafts and records everything; sole decider. |
| Claude Code session | Reads `AGENTS.md`, the decision log and the glossary before building; stops on an open decision. |

## 4. Goals and non-goals
**Goals**
- `decision-log.md` and `backlog.md` exist, are complete and are the only sources of decision state and ADR numbers.
- Decision Day outcomes recorded and linked to artefacts.
- Glossary merged before the first Accrued backend PR.
- M1 ADR drafts merged as proposed with numbers and accept-by dates.

**Non-goals**
- Guard checks, L12 rule, ESLint rules, nav constant and the C1 consumer test (F-02-T07 to T12).
- Pre-allocation of ADR-116 to 130, reservation issues, two-handle deciders, meetings and approvals (void).
- Accepting P-17, P-26 and P-29 (they land as `proposed`).

## 5. User stories and acceptance criteria
### Story A1: one in-repo decision log (F-02-T01)
- **AC-1** Given chapter 09 section 9.3 and chapter 01 section 1.9, when T01 lands, then `docs/product/decision-log.md` has 101 rows (DEC-01 to DEC-99, proposed DEC-100 and DEC-101), each with: ID, decision, recommended answer (one line), owner (chapter 01's where section 1.9 lists the row, else chapter 09's), effective decide-by (chapter 01's date where it differs, with chapter 09's date in a note), default-on-silence eligibility, status (`open`, `decided`, `defaulted`, `re-dated`, `deferred`), artefact link, and the screens and epics it blocks.
- **AC-2** Given a row whose decision spends money or signs a contract, needs counsel or a CPA, or is a red-zone ADR (DEC-03, DEC-17, DEC-22 commercial part, DEC-25, DEC-26, DEC-52, DEC-71, DEC-72, DEC-77, DEC-85 and every red P-ADR), then its eligibility column reads "never defaults" and the row stays `open` past its date until the builder records it.
- **AC-3** Given the repository is still public, when T01 runs, then it opens no issue; any DEC issues (DEC-01 to DEC-19, label `decision`, recommended answer pasted) are opened only after the repository is private. In solo mode the log is the binding index and issues are optional.

### Story B1: ADR backlog adopted, one source of numbers (F-02-T02)
- **AC-4** Given chapter 09 section 9.4.2 and the six new proposals (P-64 to P-69), when T02 lands, then `docs/adr/backlog.md` has 69 rows (P-01 to P-69) with drafter, owning epic, ADR number, and draft and accept-by sprints. Numbers are the next free number on `main` (AMENDMENT-solo section 8); the plan's pre-allocation of ADR-116 to 130 by issue is superseded, and no reservation issues are opened.
- **AC-5** Given other epic specs quote ADR numbers that disagree, then `backlog.md` is the only source of ADR numbers, and epic specs and sessions cite the P-ID until `backlog.md` lists a number.
- **AC-6** Given `validate_docs.py` fails an index row in `docs/adr/README.md` that has no ADR file, then reservations live only in `backlog.md`; a README row is added when the ADR file lands, and `validate_docs` stays green.
- **AC-7** Given an ADR is abandoned, then its number is burned, never reused, and `backlog.md` marks it `withdrawn`.
- **AC-8** Given a proposal, then its accept-by is the sprint before its first consuming epic opens, unless an external clock or a section 1.9 date is earlier (vendor clock P-26 Dec 4; M1 drafts Oct 30; P-29 Dec 14 to 18 bundle).

### Story A3: sessions stop on open decisions (F-02-T03)
- **AC-9** Given `AGENTS.md`, when a session starts a screen task, then the instructions tell it to search `docs/product/decision-log.md` (and open `decision` issues, if any exist) for its screen IDs, and to stop and ask if one is open.
- **AC-10** Given DEC-20 is open and lists BND-01 in "Blocks", when a session is asked to build BND-01's `client_service` actions, then it stops and asks (dry run recorded in the task's progress log).

### Story C1: one glossary change set (F-02-T04)
- **AC-11** Given chapter 09 section 9.5, when T04 lands (target Thu Oct 29, hard date Fri Oct 30, DEC-14), then `docs/product/glossary.md` contains: the four header rules (9.5.1); all 24 amendments (9.5.2); the three reserved-word changes for Task, Audit and Document (9.5.3); every addition row of 9.5.4 grouped by owning module; the legacy rename-or-freeze table (9.5.5); a pointer to the status bridge (9.5.6) that matches `status-vocabulary.yaml` (C2); the copy-ban index pointing at L1 to L12 (9.5.7); and the entry "Abacus: internal code namespace; never user-facing" (P-01).
- **AC-12** Given chapter 01's DEC-14 position, then the glossary also states: "to-do", never "task", for assignable work; "Document" as a UI label only in Files and the portal; `sign_off` distinct from `review_decision`; and the SPEC-022 board's name as decided (R-07 answer below).
- **AC-13** Given the glossary keeps `client_user`, `approval`, `reminder` and similar in its "Don't use" columns, then each column is machine-readable (backticked identifiers, comma-separated) so the L12 ban list can be generated from it.
- **AC-14** Given the glossary is a hot file, then it merges ahead of F-03's first Accrued backend PR.

### Story A2: Decision Day, Fri Oct 23, as a solo decision session (F-02-T05)
- **AC-15** Given drafts exist by Thu Oct 22 for P-02, P-38, P-01, P-03, P-04, P-05, P-34, P-36, P-39, P-54 and P-55, when the pack is assembled, then each agenda row links its draft or its chapter-09 row.
- **AC-16** Given the session on Fri Oct 23, when it ends, then every row in Blocks A and B is `decided` (with its artefact) or has an owner and decide-by in `decision-log.md`; the five chapter-01 amendments (DEC-05 dates; DEC-65 and conflict X-10; continuous calendar; epic keys EP-01 to EP-28 to canonical epics; DEC-100 and DEC-101), the parity-tier reading, the new proposals P-64 to P-69 (as rows added to chapter 09 section 9.4.2, or their rejection) and the ADR-numbering erratum are recorded; chapter 01 sections 1.2.1 and 1.3.3 carry the parity-tier wording decided; and M0 is met. Default-on-silence applies; its three never-default kinds are adopted.
- **AC-17** Given a decided row, then its decision-log entry links the binding artefact (ADR, SPEC, glossary, YAML), and any DEC issue is closed with that link.

### Story B4: the M1 orphan ADR drafts (F-02-T06)
- **AC-18** Given M1 requires the e-signature ADR by Fri Oct 30, when it merges as `proposed`, then P-26 (DEC-25) records record mode first, then DocuSign embedded with provider-hosted ID Verification behind an `EnvelopeProvider` port, KBA required for the 8879 family, SMS refused, handwritten fallback after three failures, human-only send, envelope policies as data.
- **AC-19** Given P-26 needs counsel, then the PR requests counsel review through F-09's engagement and its accept-by is Dec 4 (DocuSign go/no-go); if counsel has not answered, DEC-25 falls back to record mode only.
- **AC-20** Given the write-capability ADR, when it merges as `proposed`, then P-17 (DEC-46) records the red `integrations` module, three ownership modes, a protected `write-capabilities.yaml`, human-approved idempotent writes with a dry run and write-once evidence, and `connections` staying read-only.
- **AC-21** Given the busy-season ADR, when it merges as `proposed`, then P-29 records per-firm windows from first real data (Jan 1 to Apr 20; Sep 1 to Oct 20 for tax or EBP firms), mini-freezes, no promotion in deadline weeks and no year-one exception (chapter 01 section 1.2.4).
- **AC-22** Given the three drafts, then all three ADR files merge as proposed by Fri Oct 30 and `backlog.md` records their numbers and accept-by dates: Nov 27 (P-17), Dec 4 (P-26) and the Dec 14 to 18 bundle (P-29).

### Story B4b: the clock and scenario ADR (F-02-T13)
- **AC-23** Given F-04 opens in S1 with `kernel.clock` (F-04-T02) and DEC-27 / P-37's decide-by is Fri Oct 30, when the ADR is drafted from chapter 03's text, then P-37 records `kernel.clock` (`now`, `today`, `system_now`, `frozen`) with production refusal, the tenant demo clock on synthetic firms only, `scenarios/brightwater_hale` loading through service APIs, and `firms.synthetic = true` replacing SPEC-001 AC-14's "(Synthetic)" suffix.
- **AC-24** Given the P-37 draft, then it is open by Tue Oct 27 and accepted by Fri Oct 30, before F-04-T02 starts, and `backlog.md` marks it accepted. Its red parts never default on silence.

## Task map
Plan key to the acceptance criteria it must satisfy. Stories B3, C2, D1 to D4 and A4 are not mapped yet.

| Plan key | Acceptance criteria |
|---|---|
| F-02-T01 | AC-1, AC-2, AC-3 |
| F-02-T02 | AC-4, AC-5, AC-6, AC-7, AC-8 |
| F-02-T03 | AC-9, AC-10 |
| F-02-T04 | AC-11, AC-12, AC-13, AC-14 |
| F-02-T05 | AC-15, AC-16, AC-17 |
| F-02-T06 | AC-18, AC-19, AC-20, AC-21, AC-22 |
| F-02-T13 | AC-23, AC-24 |

## 6. Behaviour and flows
Documents only. The builder records decisions in `docs/product/decision-log.md` or an ADR and carries on, defaulting to the plan's proposed option (AMENDMENT-solo section 7). ADR numbers are the next free number; cite P-IDs until `backlog.md` lists one.

## 7. Domain and data changes
N/A beyond what the criteria name; this slice changes no product tables unless an AC says so.

## 8. Interfaces
N/A beyond what the criteria name.

## 9. Authorisation and tenancy
N/A: repository, documentation and contract tooling; no tenant data is read or written by the slice. Where an AC names a matrix action, the standard `authorise()` and agent-deny rules apply.

## 10. AI behaviour
N/A: no model calls.

## 11. Integrations
N/A except where an AC names GitHub Actions, `gh` or a hosted database.

## 12. Edge cases and failure modes
- A DEC row is never-default (money, contract, counsel, red ADR): it stays `open` past its date until recorded.
- Counsel has not answered on P-26: fall back to record mode only (AC-19).
- P-37 slips past Oct 30: F-04-T02 waits.
- An ADR number quoted in a spec disagrees with `backlog.md`: `backlog.md` wins and the number is void (AC-5).

## 13. Security and privacy
- **Data classification:** internal planning documents. The repository stays public: never commit a secret or real client data; vendor, region and key-handling decisions are recorded at the level the plan already states.
- **Threats considered:** exposing sensitive operational detail in a public repository.
- **Mitigations:** keep drafts to the plan's text; no credentials in any ADR.

## 14. Audit trail and evidence integrity
Every decision is recorded in `docs/product/decision-log.md` or an ADR. Generated files are never hand-edited.

## 15. Observability
N/A.

## 16. Performance and scale
Only the CI time budgets named in the criteria.

## 17. UX
N/A: no screens.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 | review | Count the rows (101) and check every column is filled. |
| AC-2 | review | The listed rows read "never defaults" and stay open. |
| AC-3 | review | No issue opened while the repository is public. |
| AC-4 | review | 69 rows in backlog.md; numbers are next-free; no reservation issues. |
| AC-5 | review | Grep epic specs for ADR numbers not in backlog.md. |
| AC-6 | integration | `validate_docs` passes with backlog.md present and no orphan README rows. |
| AC-7 | review | A withdrawn row is marked `withdrawn` and its number is not reused. |
| AC-8 | review | Each row's accept-by follows the sprint-before rule or names the earlier clock. |
| AC-9 | review | AGENTS.md text names decision-log.md and the stop rule. |
| AC-10 | review | Dry run with DEC-20 open and BND-01 requested; session stops and asks. |
| AC-11 | review | Check each glossary section against chapter 09 section 9.5. |
| AC-12 | review | Four statements present. |
| AC-13 | unit | The Don't-use columns parse (backticked, comma-separated). |
| AC-14 | review | Glossary merged before the first F-03 backend change. |
| AC-15 | review | Agenda pack links every draft. |
| AC-16 | review | Walk Blocks A, B and C; M0 recorded. |
| AC-17 | review | Each decided row links its artefact. |
| AC-18 | review | ADR-P-26 file contains each listed point. |
| AC-19 | review | Counsel request recorded; fallback stated. |
| AC-20 | review | ADR-P-17 file contains each listed point. |
| AC-21 | review | ADR-P-29 file contains each listed point. |
| AC-22 | integration | `validate_docs` passes; backlog.md lists numbers and accept-by dates. |
| AC-23 | review | ADR-P-37 file contains each listed point. |
| AC-24 | review | Dates met and backlog.md marks it accepted. |

## 19. Rollout
No feature flag unless an AC names one. Changes land on `main` once `make check` is green; staging is deployed once at sprint close (AMENDMENT-solo section 9).

## 20. Open questions
All answered with the plan's proposed option.
- [x] Is P-25 (model-drafted text to clients) accepted on Oct 23? Record the decision on Oct 23 (off per firm, human-edited and human-sent only); write and accept P-25 before N-03 (S55).
- [x] SPEC-022 board label (R-07): move the file as chapter 09 says; glossary term "Evidence board" for the legacy concept; binder surfaces keep the handoff's "Requests" label.
- [x] Mirror the plan under `docs/product/plan/` (R-11)? No: the decision log is the binding index.
- [x] Interpretation of "acceptance one phase before the line that needs it" (R-15): the sprint before the first consuming epic opens, unless an external clock is earlier.
- [x] P-64 to P-69 (R-05): confirm and add to chapter 09 section 9.4.2 on Decision Day; until then cite P-68 and P-69 by name.
- [x] Counsel for P-26 (R-13): request through F-09's engagement; fallback is record mode only.
- [x] Are DEC issues still opened: no; the decision log is the index and issues are optional (AC-3).

## 21. Future / explicitly deferred
- Story B3 (decider integrity checks), C2 (glossary binds identifiers), D1 to D4 (scope guards, nav, banned terms, Single audit), A4 (S1 to S2 burn-down): add ACs when F-02-T07 to T12 task files are written.
- Accepting P-17, P-26 and P-29.
