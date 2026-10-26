---
name: pen-finding
description: Handle one pen-test finding from intake to closure: record it (results only, never client data), triage within 2 working days (severity, owner, lane), fix in its own PR, add a regression test that fails on the pinned build and passes on main, and close only on the tester's retest. Use for any pen-test finding, delta or annual test (Q-03-T034, T041, T042 and later remediation rows).
---

# Pen-test finding

**Protocol of record:** `docs/ops/pentests/README.md`. Environment and build pin: `docs/ops/pentests/<window>-environment.md` and `docs/ops/gates/pen-test-1-readiness.md`.

## Never
- Paste the tester's evidence into the repository: no client data, names, amounts, tokens, cookies, session ids, hostnames, account ids or screenshots with data. Record route, request shape, response code and the weakness class; the rest stays in the vault as `V-…` references. The repository is public.
- Close a finding on your own test. Closure is the tester's retest result.
- Weaken a test or a threshold to make a fix pass (AGENTS.md rule 13).

## Steps
1. **Record** the finding as `PT<n>-<NN>` in `docs/ops/pentests/<yyyy-mm>-findings.md` (columns in the README). Status `new`, the tester's severity as given.
2. **Triage within 2 working days:** our severity (critical, high, medium, low, info; say why when it differs from the tester's), owner, lane (critical: hotfix lane, fixed within 5 working days; high: own PR in the batch by the window's deadline; lower: a dated sprint). Status `triaged`.
3. **Task file** `work/tasks/TASK-NNNN-pt<n>-<nn>-<slug>.md` with the remediation row as `plan_key`. Red module: plan first, security review of the diff before pushing.
4. **Fix** in one PR whose title starts with the finding id. Log the defect in `docs/quality/escaped-defects.md` with the layer that should have caught it; close the class where a generated test or lint rule can.
5. **Regression test** (critical and high; medium when testable) in `backend/tests/security/` or the owning suite, `test_pt<n>_<nn>_<behaviour>`, written in a separate session with the `ac-test-author` skill from the finding record, never the fix. Run it on a checkout of the pinned SHA (it must fail) and on main (it must pass); record both result lines on the finding row.
6. **Retest:** status `retest-requested`; ask the tester through the rules-of-engagement channel. On their result, status `closed` with the date, or back to `fixing`.
7. **Accepted risk** needs a DEC row with the reason and a review date; `not-a-finding` needs the evidence (for example DEC-43's 404 for a walled client).
