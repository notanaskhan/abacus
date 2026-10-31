# Penetration tests deferred (DEC-1389)

Decided 2026-11-01 by Ayush: **no penetration test runs for now**. Pen test #1, deltas #1 and #2,
pen test #2, the annual tests and every later delta are deferred until a decision books one again.
This file is the record for every sprint session: before building a row that names a pen test, a
delta, a vendor window, findings, a retest or an attestation letter, look it up here.

## The rule for a sprint session

1. **A row in "Deferred in full"** is not built. Its backlog `status` reads `deferred`. Leave it,
   say so in the sprint's kickoff scan, and do not count it as a gap.
2. **A row in "Build the rest"** is built without its pen-test clause: everything else in the row
   ships; the clause named in the table stays open and is reported as deferred, not as done.
3. **Security work that stands on its own is not deferred**: threat-model refreshes, ASVS
   self-assessments, security suites, source-assisted reviews, WAF and rate-limit settings, the
   pen-finding protocol. Build them as planned; only their tie to a test window drops.
4. **No go-live gate is waived by this decision.** Where a flip or milestone requires a closed pen
   test ("delta #1 closed", "no real-firm flag flips until closed", "enabled after the delta pen
   test"), that clause stays open and blocks that flip until a new decision either books the test
   or waives the clause for that flip. A session never treats "deferred" as "closed".
5. A row not listed here that turns out to depend on a pen test: apply the same rule, add it to
   this file and to DEC-1389's list in the same PR.

## Deferred in full (backlog `status: deferred`)

| Kind | Rows |
|---|---|
| Vendor, SOW, booking, window, findings intake, closure letter | F-09-T37, F-09-T42, F-09-T43, F-09-T90, F-09-T116, F-09-T123, F-09-T137, F-09-T147, F-09-T153, F-09-T157, F-09-T191, F-09-T198, F-09-T205, R-02-T18, A-09-T17, Q-03-T357 |
| Scope packs, readiness gates and consolidated scopes for a window | Q-03-T019, Q-03-T099, Q-03-T122, Q-03-T166, Q-03-T174, A-02-T36, A-09-T40, N-02-T39, T-01-T38 |
| Delta tests booked by feature epics | A-07-T46, P-10-T53, T-04-T44, T-05-T72, W-01-T20, G-03-T25, I-04-T23, N-03-T38, W-04-T26 |
| Triage, remediation and retest of findings | Q-03-T034, Q-03-T041, Q-03-T054, Q-03-T068, Q-03-T107, Q-03-T129, Q-03-T188, Q-03-T193, Q-03-T512 |
| Regression tests for findings | Q-03-T042, Q-03-T055, Q-03-T108, Q-03-T130, Q-03-T194 |

Already built before this decision (readiness hardening, kept): N-01-T24 (WAF file routes, rate
rule, size cap; #924) and R-01-T35 (portal drops; #925). Their windows are deferred with the rest.

## Build the rest (the named clause is deferred)

| Row | What is deferred |
|---|---|
| N-01-T29 | "findings fixed and retested by Fri Jul 9" and the acceptance's "no critical or high open"; per-firm flips wait on pilot firms. Built now: legacy InboxPanel and InboxAIMatch retired, the N-01 flag plan (TASK-2343) |
| Q-02-T35 | the pen-test environment and personas; Type I readiness proceeds |
| Q-02-T42 | pen test #1 triage; Type I as of Mar 1 and fieldwork support proceed |
| Q-02-T49, F-09-T102, F-09-T110, F-09-T181 | the pen-test letter and retest closure in the M7 dossier and diligence packs: listed as "not yet tested", never as passed |
| Q-03-T060, Q-03-T111, Q-03-T138, Q-03-T198, Q-03-T347 | the "pen test or delta closed with regression tests" evidence line |
| Q-04-T039, Q-04-T104, Q-04-T053, T-01-T47, N-02-T44 | the "delta closed" go-live criterion: stays open and blocks those flips (rule 4) |
| C-02-T43, C-02-T50, Q-04-T245 | the W1 delta test and "enabled after the delta pen test": the x100 load test and runbooks proceed; posting stays off (rule 4) |
| G-02-T27, A-08-T38, C-01-T52, G-04-T22, K-04-T46, R-03-T25, T-06-T48, X-02-T21, W-02-T29, N-04-T02, T-03-T02, N-04-T27 | the delta scope note, booking or findings item; the rest of each row proceeds |
| T-02-T30, P-08-T25, P-07-T25 | "on the pinned pen-test build": the suites and features ship on the current build |
| Q-01-T56 | the canary custom-domain tenant is still built; it is no longer "for pen test 1" |
| F-09-T214, Q-03-T519, Q-03-T520 | the pen-test line of the renewals calendar and close-out records: recorded as deferred |

## Not affected

Rows that mention a pen test only as context (integration and escaped-defect lanes, ADR-078
catch-up lanes, x25 and x100 load tests, Q-03-T037's pen-finding protocol, Q-03-T017's ASVS
self-assessment, the threat-model refreshes Q-03-T018, T091, T123 and T175, A-01-T32's
source-assisted review, F-09-T13) are built as planned.
