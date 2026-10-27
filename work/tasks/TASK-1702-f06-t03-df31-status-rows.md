---
id: TASK-1702
title: F-06-T03 DF-31 status rows for F-06 objects
spec: SPEC-400
acceptance_criteria: [AC-35]
risk_zone: red
status: in-review
epic: F-06
plan_key: F-06-T03
branch: s14-f06-t03
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Add the DF-31 rows F-06's kits read to `docs/product/status-vocabulary.yaml` (protected) and
regenerate the C2 outputs: generated document, signer states (with `verification_failed` shown as
"Identity check failed"), the signing-step words and the envelope purposes.

## Plan
- Checklist from F-06.md §4.2 and §4.6, DF-31, DF-11 and the screen contracts (TASK-1700):
  - generated document: drafting, draft, approved, locked; adoption is not a status (Q6); render
    status stays separate (no `out_of_date` here: P-11's call);
  - sign-off slot: signed, stale — **already in the registry** (P-04-T02), skipped;
  - envelope signer: waiting, verified, signed, declined, verification_failed ("Identity check
    failed"), with the chip and signer-band context labels TPL-16 draws;
  - signing step: Verify identity · Review · Sign · Done (derived, never stored; chip "Verify");
  - envelope purpose: e-file authorization (8879 family), engagement letter, rep letter, §7216
    consent (DF-11 sets the identity method by purpose).
- New objects sit after `envelope`, away from S13's N-01-T04 rows (after `inbox_item`) to keep the
  textual merge clean. The generated files will conflict at batch time: regenerate, never hand-merge.
- Codegen: `python -m abacus_tools.codegen.status_vocabulary`, then `--check`. No OpenAPI change: no
  endpoint uses these objects yet.
- Rollback: revert the YAML hunk and regenerate.
- Solo edition: no approval file (docs/architecture/protected-paths.md, SU-06).

## Per AC
| AC | Evidence |
|---|---|
| AC-35 | `status_vocabulary --check` clean after regen; `tests/unit/tools/test_status_vocabulary.py` and `test_review_status_registry.py` 33 passed; no hand edit to `_statuses.py` or `status.gen.ts` |

## Gotchas and discoveries
- N-02 (S13, in flight) owns the envelope family. If its C7 stub adds signer or purpose rows, the
  batch merge keeps one object and N-02's codes win where they differ; record the merge in this file.

## Progress log
- `2026-10-28` — Rows added, codegen regenerated and checked; targeted registry tests green. Contract review at batch end.

## Handoff
- **Current state:** built, PR open (stacked on F-06-T02), held for the S14 batch, after S13.
- **Exact next step:** at batch time rebase over S13's N-01-T04/N-02 registry edits and rerun the codegen.
