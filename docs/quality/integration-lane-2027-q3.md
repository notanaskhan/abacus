# Integration and conflict lane, 2027 Q3 (Q-03-T163; part 1 of 3)

The lane takes what a batch breaks between task branches: red batch and `main` runs, hot-file and
regenerated-file conflicts, migration renumbering, and cut-over defects across epics (the
client-facing pilot, the tax pilot, the Sep-Oct window). Acceptance: every red batch run of the
period is resolved within one working day, and no generated file is hand-merged. The rules are the
Q2 record's (`integration-lane-2027-q2.md`); this record adds what the S24 and S25 batches taught.

The build runs ahead of the plan's calendar: the period here is the build's, from the Q2 record's
measurement (2026-10-30) to 2026-11-03; the 2027 Q3 period proper is measured the same way from
Jul 1, 2027.

## Measurement

`python -m abacus_tools.ci.integration_lane --runs runs.json --since 2026-10-30` on the last 500
`ci` runs (fetched 2026-11-03). Two changes to the tool in this task (DEC-2080): the solo
edition's batch branches (`s<NN>-end-pass`, `s<NN>-integration`) count, and a push run on a
branch other than `main` counts neither way, because CI skips its stages there and its "success"
proves nothing.

| Branch | First red | Red runs | Resolved by | Working days | Within 1 day |
|---|---|---|---|---|---|
| `main` | run 41020846832 (`aa48f55c`) 2026-10-30 08:12 | 29 | **still red** | 2.18 | no |
| `s25-end-pass` | run 41600040024 (`9c77eeae`) 2026-11-03 08:56 | 1 | **still red** | 0.15 | yes |

**The lane is not met.** `main` has had no green `ci` run since `aa48f55c` (2026-10-30 08:12):
29 runs failed and 19 were cancelled as superseded. The S24 and S25 batches were merged with CI
skipped on the owner's decision (2026-11-03), and the S25 end pass's last red (`9c77eeae`, run
41600040024) was fixed but its re-run was cancelled under the same decision. The streak closes only
when a `ci` run on `main` completes green: one run on the current head is the next step.

## Incidents handled in this lane

| Date | Batch | What broke | Layer that should have caught it | Fix |
|---|---|---|---|---|
| 2026-11-02 | S25 (#1075-#1104, #1106) | 27 stray row-branch runs force-cancelled; GitHub left them queued about 2.5 hours, and #1106's run waited behind them | none: an Actions queue | wait; push merge commits to row branches only once, at the batch's end |
| 2026-11-02 | S25 | G4's provider (A-04-T43) ended Fieldwork's record mode under the seed loader and the A-01 tests: 96 failures in one run | integration, at the row (ED-303) | the loader writes a recorded move into a gated phase as the seed-only advance (DEC-2078) |
| 2026-11-03 | S25 | gallery visual regression red on every run: the status map grew with S25's statuses and moved every specimen after it by a fraction of a pixel | none: the regression has no way to accept a reviewed change | the `visual-change` label (below) |
| 2026-11-03 | S25 | fixture journeys cancelled at the job's 15-minute limit | none: the suite outgrew one runner | two shards (below) |
| 2026-11-03 | S25 | a stacked child's merge with `-s ours` after each parent's squash kept every row's tree exact, and 30 PRs merged in about 9 minutes | rule 4 (diff against the reviewed tree) | tree checked against each head before every merge |

## Changes to the lane's tools (DEC-2080)
- **`visual-change`.** A pull request labelled `visual-change` accepts its gallery diff after review:
  the screenshot regression reports the diff in the `gallery-visual-report` artifact instead of
  failing, as it already does on a push to `main`. Tier A and Tier D parity still block. Re-run
  the job after adding the label. Put the label on only after looking at the diff: it is the
  review, not a bypass.
- **Two journey shards.** `stage 2 fixture journeys` runs as two shards (`--shard=1/2`, `2/2`;
  106 and 85 of the 191 journeys), each inside the 15-minute limit, so the limit does not grow.
