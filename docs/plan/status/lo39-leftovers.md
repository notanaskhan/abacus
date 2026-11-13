# S0–S38 leftovers, lo39 chain (2026-11-13)

Ayush's chain over the inventory's leftover rows (`S0-S38-leftovers-inventory.csv`, refreshed on main
41be01263): cut the solo rituals, build the real work, the buildable rows, the code partials, the
test and ops partials, then the not-built rows; build first, one stacked PR per row, tests and a
three-agent security review at the end, one merge with a single CI run.

## Rows

| Row | Now | What was done (PR, TASK) | What stays open |
|---|---|---|---|
| 91 solo rituals | cut | #1861, TASK-7819, DEC-4818; `S0-S38-rituals-cut.md` | — |
| Q-04-T014 | todo | the pilot operating model doc exists (`docs/ops/pilot/README.md`) | the shared inbox, office hours and a test request need the desk (Ayush) |
| Q-04-T020 | partial | `docs/ops/on-call.md` exists | the test page needs the paging tool |
| N-02-T40 | partial | #1863, #1900: SIG-01 a, b, c, f on the full stack | SIG-02, ENG-04 (no in-app entry to a seeded draft), POR-06 g (no declined envelope), hosted runs |
| N-02-T46 | partial | RB-18 rehearsed locally (10 passed) | the staging rehearsal |
| Q-04-T107 | partial | solo walk on PF-X1 (`docs/ops/rehearsals/2026-11-13-runbook-walk.md`); DEC-4822 (TASK-7830): flip and rollback runbooks walked, two gaps fixed | the pilot onboarding runbook (RB-37) walk |
| Q-04-T137 | todo | — | the next quarter's walk |
| Q-04-T125 | partial | #1864, #1900: `abacus_tools.dark_merge_audit`, `deploy/live-paths.yaml`; run over today's batch | the Jan 25-27, 2028 trains |
| Q-04-T035 | partial | — | the custodian's ScheduleKeyDeletion on AWS; counsel's exit terms |
| F-09-T192 | partial | — | each real firm's content agreement |
| Q-03-T179 | done | #1876, TASK-7826: 44 tests; local mutmut 91–100% | the weekly run on main confirms |
| Q-03-T180 | todo | — | adding integrations and consents as scopes is Ayush's (edit-hook protected) |
| Q-03-T230 | partial | #1866: the fakes register names the DocuSeal fake | sandbox verification needs credentials |
| F-01-T06 | partial | — | the ruleset (Ayush) and five green main runs |
| F-01-T07 | partial | #1867, #1900: stage 1 path-aware and fail-closed | the 6-minute timing on the next frontend-only PR |
| P-03-T20 | partial | — | the handoff's prefill wording (DEC-460) |
| P-04-T47 | partial | — | staging |
| P-09-T08 | done | #1868, #1900: a withdrawn version never resolves | — |
| P-09-T09 | partial | — | a runtime step mode (P-10) and triggers |
| P-09-T11 | partial | #1871, #1900: the trace PDF | a real WeasyPrint render (CI Linux) |
| R-02-T13 | partial | — | `make seed-demo` against the fixtures on a Linux host |
| F-01-T05 | partial | #1883, #1900: main's reds fixed at their causes | E0 and Sep 24 fixtures (Linux), the `pii_reveals` microsecond flake (a migration), coverage 95% |
| Q-03-T036 | todo | — | Ayush's call on the perf stack's records bucket (COMPLIANCE lock) |
| A-05-T02, T-04-T08 | todo | — | Claude Design revision boards (the R3 prompt pack is ready) |
| The other test and ops partials (J) | unchanged | — | a visual run and sign-off (Tier C locks), a reviewing CPA (A-06-T08), hosted sweeps, the deferred pen test (T-02-T30), the perf stack (Q-03-T046) |

## For Ayush

- **Q-03-T180:** add the scopes by hand (the edit hook refuses an agent's edit). In
  `backend/pyproject.toml` `[tool.mutmut] only_mutate`, add `"src/abacus/modules/integrations/*"` and
  `"src/abacus/modules/consents/*"` (or the module that holds consents); in
  `backend/src/abacus_tools/quality/mutation.py` `SCOPES`, add `"integrations": ("src/abacus/modules/integrations/*.py",)`
  and the consents scope; then `backend/mutation-thresholds.yaml` gets each at 0 until its first run.
- **Q-03-T036:** choose how the perf stack treats COMPLIANCE-locked records (a long-lived
  `abacus-perf-records` bucket, a perf-only retention mode, or no record-writing scenarios).
- **F-01-T06:** the branch ruleset requiring stage 1 and stages 1 and 2.
- **Q-04-T107:** decided 2026-11-13: synthetic firms only (DEC-4822, TASK-7830).
