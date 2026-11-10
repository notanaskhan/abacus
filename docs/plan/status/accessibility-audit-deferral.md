# Accessibility audits deferred; no live pilot firms (DEC-1391, amended by DEC-1530 and DEC-4100)

Decided 2026-11-01 by Ayush: **no external accessibility audit, and no in-house accessibility
audit, for now.** Both wait for a decision that books one. Same date, a standing fact: **no pilot
firm is live.** This file is the record for every sprint session, beside
`pen-test-deferral.md` (DEC-1389).

## Accessibility audits

### The rule
1. **A row in "Deferred in full"** is not built. Its backlog `status` reads `deferred`; a kickoff
   scan lists it as deferred, never as a gap.
2. **A row in "Build the rest"** ships without its audit or Accessibility Conformance Report (ACR)
   clause; the clause stays open and is reported as deferred.
3. **Automated accessibility checks in the build are not deferred.** axe in screen tests and
   journey specs, the parity locks' axe runs (for example N-02-T43), keyboard suites, forced
   colours, reduced motion and the 390 and 320 reflow checks are part of building a screen. Write
   them as planned. Only a manual audit (VoiceOver and NVDA walks) and the ACR wait.
4. **No go-live gate is waived.** "Portal ACR with no open AA failure" (M10) and "full-product ACR"
   (GA) stay open and block their milestones until a decision books the audit or waives the
   clause. A session never treats "deferred" as "issued".

### Deferred in full (backlog `status: deferred`)
| Kind | Rows |
|---|---|
| Booking the external auditor | Q-03-T073, Q-03-T455 |
| Audit support, remediation from the audit and the ACR | Q-03-T104, Q-03-T109, Q-03-T484, Q-03-T493, Q-03-T502 |
| The in-house re-audit and ACR addendum | Q-03-T289 |

### Build the rest (the named clause is deferred)
| Row | What is deferred |
|---|---|
| Q-03-T111 | "portal ACR with no open AA failure" in the M10 quality evidence (rule 4) |
| Q-03-T518 | "full-product ACR" in the M23/M24 evidence (rule 4) |
| N-03-T47 | the ACR addendum for POR-07 and POR-12; the other docs ship |
| Q-03-T397 | the full-product accessibility audit call-off in the 2029 vendor plan (its pen-test deltas are deferred by DEC-1389) |

A row found later that depends on an accessibility audit: apply the same rule, add it here and to
DEC-1391 in the same PR.

## No live pilot firms

This is a fact, not a deferral: no firm uses the product yet (only the synthetic Brightwater Hale
tenant and the Dev tenant). Rows whose acceptance needs a live firm cannot finish until one
exists. About 160 backlog rows mention pilot firms, per-firm flips, shadow runs or champions; they
are not listed one by one.

1. **Build the code part of such a row** (routes, flags, checklists, scripts, runbooks, dossier
   templates) as planned.
2. **Leave the firm part open**: per-firm flag flips, shadow scoring and exit evidence, champion
   confirmations, go-live checklists signed per firm, founding-price invoices, support reserves for
   a live shadow. Report it as "waiting on a live firm", never as done, and never fill it with
   synthetic or invented firm evidence (AGENTS non-negotiable 16: the seed writes only the
   synthetic tenant).
3. A flag whose retirement waits for "on for every live firm" is renewed on its calendar
   (`flag-renewals-2027.md`) rather than retired.

Sprint 18's rows in this state: N-01-T29 (per-firm flips, flag retirement), Q-03-T112, Q-04-T038,
Q-04-T039, F-09-T144, F-09-T145, Q-03-T111, Q-04-T040, Q-04-T041, Q-04-T042 and Q-04-T348 (it
retires `compliance.legal_holds` after confirming the routes are on at every live firm).

## The test pilot firm, PF-X1 (DEC-1530, amends rule 2)

Decided 2026-11-01 by Ayush: instead of waiting for a live firm, the ops rows run against a seeded
synthetic test firm. **PF-X1 is Brightwater Hale**, the synthetic tenant the seed already writes
through the service APIs (AGENTS non-negotiable 16 holds: no new firm content in code). It carries
the pilot facts the go-live tooling reads:

| Fact | Where |
|---|---|
| Pilot code PF-X1, `synthetic: true`, no `real_data_since` (no window ever applies; the platform's guards stay inert, DEC-68) | `deploy/windows.yaml` |
| Go-live dossier, marked as the test firm | `docs/ops/go-live/PF-X1.md` |
| Pilot enrolments in shadow (the Feld 2025 return, Northwind's EBP audit), window Sep 1, 2026 to Oct 20, 2027, baseline 14 days | `make seed-staging` with `--slice pilot` (`brightwater_hale/pilot.py`) |
| Weekly `pilot_metric_snapshots` | `make pilot-metrics FIRM=293fc3e7-be13-4767-ae6a-ce245b2dbda9 WEEK=<Monday>` |

**Rule 2 now reads:** the firm part of a row runs on PF-X1 where the test firm can carry it, and is
reported as PF-X1's ("rehearsed on PF-X1, synthetic"), never as a live firm's. What PF-X1 carries:

- per-firm flag flips through `make flag` and flip requests (the flip guard treats PF-X1 as a pilot
  firm: an approver who is not the operator, and a rollback link);
- `make go-live-check` runs and `go_live_dossier fill`, every level;
- shadow runs and their scoring (`make shadow-report`), on the synthetic returns and audits;
- enrolments, mode moves and the W4 to W7 snapshots and their reads (Q-04-T050, Q-04-T054);
- runbook and rollback rehearsals, canary and journey walks, evidence packs assembled from them,
  each labelled synthetic.

**Widened on 2026-11-10 (DEC-4100).** Ayush, as an internal test of progress: every S0–S25 row
whose acceptance needs a pilot firm runs on PF-X1, including the clauses DEC-1530 left open. The
list, with what each row needs and where it stands, is `PF-X1-runs.md`.

- Brightwater Hale is **extended, not copied**: its scenario gains the synthetic files, inputs and
  data the rows need, through service APIs and import endpoints only (AGENTS rule 16; no kit sample
  data, DF-35). A second firm would collide on the scenario's global ids, so a row that names a
  second or third firm runs once, on PF-X1, and records that the others are not there.
- **The clauses DEC-1530 left open now run synthetically too:**
  - `tenant.real` and `go_live_dossier check --ready`, as a labelled rehearsal
    (`go_live --rehearse-real`; `check --ready --rehearsal`). Plain `--ready` on PF-X1 still fails;
  - signed MSA, DPA and pilot terms, as synthetic documents marked SYNTHETIC on every page and
    never sent anywhere;
  - a firm person's confirmations (system of record, shadow-rules acknowledgement, champion memos,
    window notices), given by Brightwater Hale's seeded people;
  - CCH reconciliation, against the fake CCH (`abacus_tools/fakes/cch_axcess.py`);
  - founding-price invoices, as a synthetic record with no amount (the decision log's money rule).
- **Labelled:** every such run reads "synthetic (PF-X1)" in its record and in `status-verified.csv`,
  never as a live firm's.
- **Comes back:** the real-firm version of each clause is a go-live check for the first real firm
  that signs, listed in `docs/ops/go-live/PF-X1.md` §Real-firm go-live checks. A real firm gets its
  own dossier and never inherits PF-X1's evidence.

**Still not synthetic** (stays open, with the person who acts named):

- what DEC-2098 keeps with the founders: a counsel review or advice, a vendor contract, a price, a
  hire, and a founder's own signature on a dossier (the sign-off table);
- rule 3: a flag waiting for "on for every live firm" still waits; PF-X1 is never a live firm;
- what needs a hosted stack (staging journeys, `make seed-staging`, real SES and DNS, the paging
  tool): partial, with the command for Ayush in `PF-X1-runs.md`.

**Untouched:** every gate DEC-1389 keeps open (pen test #1, deltas #1 and #2, "delta #2 closed" in
T-01-T47's pack) and rule 4 above.

A real pilot firm is added beside PF-X1 with its own code, `real_data_since` and dossier; PF-X1
stays as the rehearsal firm.

