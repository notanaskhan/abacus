# S28 end pass (TASK-3334; DEC-2325)

One review after the build, on the S28 stack (#1230 onward), with #1229 merged into the tip so the
results aren't hidden by main's older reds. Run 2026-11-05 on a laptop. CI results are added below
when the one run finishes.

## Results
| Check | Result |
|---|---|
| `make check-fast` (ruff, pyright, import contracts, banned patterns, error codes, docs, scope guards, secrets, generated files, migration heads) | Pass |
| Backend unit, property, acceptance, connectors, golden, contracts and workflows | 50,559 passed, 2 failed: `test_classification` needs `libgobject`, absent on this laptop. Both pass with `weasyprint` stubbed; CI has the library |
| Backend integration | Targeted only, about 1,300 tests in the files that touch S28's tables and modules: all pass, 1 xfailed. The full suite is CI's |
| Web | 3,158 passed; tsc, eslint and prettier clean |
| `packages/ui` | 1,299 passed; tsc and prettier clean |
| Replay histories | Recorded and replaying: `notice-response-v1`, `section-draft-v1`, `upload-processing-v8`, `form-extraction-v1` |
| Migrations 0667 to 0669 | Up, down and up pass on a small database. That isn't Q-03-T189's x100 rehearsal |

## Gallery specimen diff, accepted
CI's visual regression failed on 47 specimens. The new `ebp_participant_loan` group grows C-06's status map by 92 px, and every specimen below it moves by a subpixel, so its height reads 2 px more or less. `status.gen.ts` is the only file changed under `packages/ui`, and nothing else in `apps/web/src/gallery`. #1265 carries the `visual-change` label for this (DEC-2080).

## Not run
- **Tier C parity and axe.** AUD-10, AUD-17, EBP-06, NOT-03 and TAX-13 have no parity rows, so A-04-T38's parity clause is open. The keyboard test passes.
- **Mutation measurement for `assurance/compute`** (A-04-T41). CI's floors job checks that no floor dropped; the new engines don't raise one yet.
- **Evals on a real model.** `notices_responder` runs on the fake model only; its labels aren't CPA-reviewed (DEC-2312).
- **Staging clauses.** p95 (A-04-T41), the Whitley send (N-04-T16) and the planning rehearsal (A-04-T39) wait for a staging deploy.

## Review findings, fixed
| Finding | Severity | Fix |
|---|---|---|
| `notice_agency_replies.evidence_version_id` has no key, and the service took any id, so a reply could cite another engagement's version across an ethical wall | High | The service checks the version's engagement and answers 404 |
| The Create notice route started the timers after commit: Temporal being down failed a committed notice and lost its timers | Medium | A `notice.created` event starts them through the outbox |
| 0669's downgrade dropped `release_date` before the generated column that depends on it, so every down failed | High | Generated column first |
| `ebp_certification_point` events had no registered owner, so the audit explorer hid them | Medium | Owners registered |
| Four screens used a colour class that isn't a token (`olive`), so those marks drew no colour | Low | `green` tokens |
| EBP-06's Unadjusted layer showed a dash where the contract says 0.00 | Low | Explicit zero on that screen |

No other finding in the red diffs: forced RLS and column grants on 0667 to 0669, the archive freeze trigger, one original release per work item, human-only decision rows, statements authorised by the version's own engagement, certification sign-off failing closed, the OCR gate failing closed for §7216, the sealed confirmation and reply note, and the responder's output checks.

## Screens held at `planned` in the manifest (DEC-2325)
The links rule fails a built screen with an unwired designed link, so these stay `planned` as NOT-02 does, though every artboard ships as a fixture scenario with a test:
- **AUD-10, EBP-06:** cockpit canvases with no path, so their rail links to each other and AUD-11 have no builder.
- **NOT-03:** FIL-01's hold doesn't name its notice.
- **TAX-13:** the row doesn't carry the client and engagement for Thornbury's CLI-07 link.

## Quality lanes
- **Q-03-T190, Q-03-T191:** this pass's fixes, listed above.
- **Q-03-T189:** still partial. No perf stack on main, and no runtime v2 schema until P-10.

Next free numbers: TASK-3335, DEC-2326, migration 0670, RB-49.
