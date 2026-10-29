# Integration and conflict lane, 2027 Q2 (Q-03-T087; part 2 of 2)

The lane takes what a batch breaks between task branches: red batch and `main` runs, hot-file and
regenerated-file conflicts, migration renumbering, and cut-over defects across epics (M8, first
shadow, N-01, N-02, delta #1). Acceptance: every red batch run of the period is resolved within one
working day, and no generated file is hand-merged.

## Rules
1. **Generated files are regenerated, never merged by hand.** On a conflict in any file listed in
   the Makefile's `GENERATORS`, the API client (`packages/api-client`), `openapi.json`, the error-code
   registry or the generated tenant-isolation test: take either side, run `make regenerate` (or the
   one generator) and `python -m abacus_tools.quality.error_codes --write`, and commit the result.
   `make check-generated` and the API client's drift check in CI refuse a hand-merged file.
2. **Migrations keep one head.** A batch that brings two heads renumbers the later branch's
   migration on its own branch (never one already on `main`); `make check-heads` refuses two heads.
3. **Registers hold each ID once.** `python -m abacus_tools.quality.register_ids` (check-fast)
   refuses a decision, escaped-defect or runbook ID twice; keep the newer version, delete the other.
4. **After the last merge of a batch, diff the tree against the reviewed tree** for every file the
   batch touched before the CI-running merge: git's auto-merge can repeat a whole block with no
   conflict (S15 group B: `signatures/api.py` `start_envelope` twice; ruff's F811 caught the code
   copy, nothing caught the doc copies until rule 3).
5. **A red batch or `main` run is resolved within one working day**: fixed forward on the batch
   branch, or the breaking PR reverted. Measure with
   `python -m abacus_tools.ci.integration_lane --runs <gh run list --json ...> --since <period start>`.

## The period's red streaks (`ci` on main and batch branches)

Measured 2026-10-30 on the run list from 2026-10-20 (the build runs ahead of the plan's calendar;
the 2027 Q2 period proper is measured the same way from Apr 1, 2027):

| Branch | First red | Red runs | Resolved by | Working days | Within 1 day |
|---|---|---|---|---|---|
| `main` | run 40232054577 (`0e75cb43`) 2026-10-25 21:15 | 1 | run 40239858669 (`d7773ffb`) 2026-10-25 22:27 | 0.00 | yes |
| `main` | run 40240957598 (`5b0649df`) 2026-10-25 23:48 | 2 | run 40242547502 (`bbe1cf37`) 2026-10-25 23:51 | 0.00 | yes |
| `main` | run 40241725151 (`7279b40f`) 2026-10-25 23:57 | 6 | run 40391406932 (`ae4fb730`) 2026-10-26 20:03 | 0.84 | yes |
| `main` | run 40417471929 (`ee7bdf04`) 2026-10-26 23:54 | 15 | run 40849655921 (`faf6d152`) 2026-10-29 10:13 | 2.43 | no |
| `main` | run 40859579036 (`c441d80c`) 2026-10-29 11:35 | 2 | **still red** | 0.38 | yes |

- The 2.43-day streak (Oct 26 to Oct 29) predates this lane: fifteen red runs on `main` from
  `ee7bdf04` (the S10 wave C batch) until `faf6d152` turned it green.
- The open streak from `c441d80c` (Oct 29): every later `main` run up to `64e465ef` (the S15
  group B batch) was cancelled for being superseded; `64e465ef`'s run decides it.

## Incidents handled in this lane

| Date | Batch | What broke | Layer that should have caught it | Fix |
|---|---|---|---|---|
| 2026-10-30 | S15 group B (#712–#738) | DEC-1053, DEC-1058 to DEC-1061 left twice in the decision log by squash merges of stacked PRs | a register-ID check (none existed) | rows deduplicated; `register_ids` added to check-fast (this task) |
| 2026-10-30 | S16 T-01 (#678, #679) | DEC-1157 in two versions (the stacked PR's revision and the original) | the same | the older version (105 objects / 495 rows) removed; the revision kept |
| 2026-10-30 | S15 group B | `start_envelope` repeated whole in `signatures/api.py` by an auto-merge | ruff F811 | removed before the CI-running merge (#731) |
| 2026-10-30 | S15 group B | a stale description left in `openapi.json` by a hand-picked side of a branch | rule 1 (`make generate`) | regenerated in #731 |
