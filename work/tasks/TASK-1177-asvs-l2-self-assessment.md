---
id: TASK-1177
title: OWASP ASVS Level 2 self-assessment of the pen-test #1 build — docs/ops/pentests/2027-02-asvs.md, every verdict grounded in main; the request-body extras check and ED-034 (Q-03-T017)
spec: SPEC-051
acceptance_criteria: [AC-1]  # the M7 gate tracker's pen-test row; Q-03-T017's acceptance is Q-03 §D1 (no spec AC of its own)
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T017
branch: s7c-pentest-readiness
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Every ASVS L2 gap is either fixed before Fri Feb 12 or listed in the scope letter as a known item." Q-03-T017; chapter 10 §10.10 ("self-assessment against an OWASP ASVS Level 2 checklist (inferred)").

## Plan (red zone)
- **Checklist:** ASVS **4.0.3**, Level 2, every chapter (V1–V14). The plan says "inferred checklist" and names no version. 4.0.3 is the version testers still report against, and its requirement ids are stable; a mapping to 5.0 is a later row's (DEC-307).
- **Verdicts:** `met` only with a file and line or a named test on `main` (d2920364), opened and read in this session. Otherwise the verdict is `partial`, `not met` or `n/a`, each with a reason. Every `partial` and `not met` names the task that closes it, or "no task: ticket" with a proposed severity. Terraform that is written but has never been applied is `partial`.
- **File:** `docs/ops/pentests/2027-02-asvs.md` holds results only, with no exploit detail and no environment addresses (Q-03-T017).
- **One code defect found:** `PUT /v1/firm/letter-policy` reads its output model, which ignores undeclared fields. That breaks the input-model rule in `docs/architecture/reference/backend-module.md` (ASVS 5.1.2). It is recorded as **ED-034** and held as a strict xfail in a new generated check, `backend/tests/unit/api/test_request_bodies.py`, which covers every JSON request body in the OpenAPI document. The fix (a `LetterPolicyIn`, `make regenerate`) is a contract change in identity and is left for its own task. It is not made here.
- **Decisions:** DEC-307 (version, verdict rules, severity mapping, known-items rule).
- **Rollback:** revert the commit.

## Progress log
- 2026-10-24: assessed V1–V14 against d2920364. Three read-only evidence sweeps (auth and sessions; access, validation, files and API; crypto, logging, data, comms, config) were spot-checked line by line before use. Twelve citations were reopened; all matched. Results: see the file's summary. ED-034 recorded; `test_request_bodies.py`: 207 bodies pass plus the count check (208 passed), 1 strict xfail. Status `in-review`: the gaps need tickets, which this session cannot open.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-307 | The plan says "inferred checklist" with no version, verdict rule or severity scale | No |
