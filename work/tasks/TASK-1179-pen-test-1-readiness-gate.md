---
id: TASK-1179
title: Pen-test #1 readiness gate — docs/ops/gates/pen-test-1-readiness.md, each §10.13 item ready or not ready with evidence on main, and the human to-dos (Q-03-T019, with Q-02-T35)
spec: SPEC-051
acceptance_criteria: [AC-1]  # the gate tracker's pen-test row; Q-03-T019's acceptance is the signed checklist on Fri Feb 12, 2027
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T019
branch: s7c-pentest-readiness
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Both founders sign the readiness checklist on Fri Feb 12 with every listed file green on the pinned SHA." Q-03-T019; chapter 10 §10.13 (pen-test readiness row); Q-03 §D1.

## Plan (red zone, a document)
- `docs/ops/gates/pen-test-1-readiness.md` (new; `docs/ops/gates/` is new):
  - **Items:** every §10.13 "must be green" item, followed by T019's own list: the pen-scope files, P-08's portal-scope and host-pinning files, DAST and the ADR-080 core. Each item gets the files that evidence it, today's state on `main` (`ready` or `not ready`), what closes it, and the task.
  - **ADR-080 core:** mapped from §10.3.4's named files to what `main` holds. Where §10.10 names a file that does not exist but the control is tested elsewhere, the row says so and is `not ready` until a reviewer accepts the mapping or the file lands (DEC-308).
  - **Q-02-T35's half:** the environment, personas and review role, taken from the environment file.
  - **Records:** a sign-off block for the pinned SHA and the signatures. A run-sheet for the pin day: the exact commands that prove each file green on the SHA.
  - **Human to-dos:** listed.
- **Decisions:** DEC-308 (what "green on the pinned SHA" means: no strict xfail in a pen-scope file, the mapping of the ADR-080 core, how a not-built surface is handled: out of scope in the letter, never "green with a note").
- No code. Rollback: revert the file.

## Progress log
- 2026-10-24: written against d2920364. Not ready today: P-08's two files, DAST, the four hostile-file strict xfails (ED-018 to ED-021, under repair in another workstream), the ADR-080 named files that do not exist, the environment itself (no compute in Terraform), the build pin and the signatures. Ready: the walls file, the generated isolation, matrix and route suites, the schema check and the threat-model refresh (pending N's review). Status `in-review`: it signs on Fri Feb 12, 2027.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-308 | §10.13 says "green" without saying whether a strict xfail, a renamed file or a not-built surface counts | No |
