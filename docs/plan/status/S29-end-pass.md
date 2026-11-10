# S29 end pass (2026-11-07)

One end review over the stack, on main 9811fd79a; head 0673, S29's chain 0680 to 0687 on top.

## Run
| Gate | Result |
|---|---|
| `tests/unit`, `tests/contracts` | 50,253 passed; 3 first-run failures fixed, then re-run per file |
| Web vitest | 3,218 passed; 1 passes alone (load-sensitive timing in `seed-fixtures`) |
| `tests/security`, S29's migrations, OCR, home activity, replays | 12,111 passed; 16 fixed and re-run |
| `make check-fast` | passes |
| New Playwright specs, fixture project | NOT-01, 02, 03, TAX-13, BND-03, keyboard: pass. j09, j18: pass on fixtures |
| `test_classification.py` | run with a stubbed `weasyprint`: this Mac has no GTK. CI runs it for real |

## Security review of the red diffs: found and fixed
| Finding | Fix |
|---|---|
| `archived_guard` would fail C13's projector on `archive.locked` itself, and delivery receipts and in-flight runs after a lock, retrying forever | `human_gates`, `messages`, `approval_grants`, `agent_runs`, `agent_run_records`, `agent_activity` exempt, each with its reason; documentation tables pinned as never exempt |
| The viewer manifest gave client principals how a page was read and the OCR refusal code | Client gets neither; retry is firm-only |
| Decline without a reason passed C18's models | Validators on `ProposedEntryDecideIn` and `PackageDecideIn` |
| `AccountRollforwardOut.total` and five C18 fields unclassified | Classified |
| `ssn_mask` on two EBP-08 rows wasn't the masked TIN shape | Renamed `identifier_mask` |

Reviewed with no change: the matrix's human-only cells, the guard's trigger logic, C13 presenters, `return_id` filtering after visibility, the safe workbook writer.

## Other bugs the pass caught
- `agent_runs_forward_only` (0010) refused every v2 review outcome after a run finished. 0680 now lets a state write through to the sync trigger's transition check; anything else on a finished run still stops.
- `on_envelope_completed` would have raised on a missing `engagement_id` from my I-01-T23 change.
- C5 v1.1's frozen `NoticeCode` was changed; it's now the additive `waiting_for_signature`.
- `NOT-02` failed axe on `aria-required-children`; roles corrected.
- EBP-05 and EBP-09 drew figures without the handoff's `$`.

## Not run
Full integration shards and e2e beyond the new specs: CI. Staging: nothing here deployed. Parity Tier C: not measured, so nothing is locked.

## Guard behaviour to know
The guard reads the work item under RLS, so a session with no tenant set, like a superuser migration, passes it. Every app write has the tenant.
