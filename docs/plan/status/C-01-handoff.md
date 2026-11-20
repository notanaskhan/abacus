# C-01 hand-off notes (C-01-T55, TASK-8757, 2026-11-20)

What each later epic can rely on from the close engine v1 (SPEC-655; contract `docs/contracts/closes.md`;
screens `docs/screens/CLS-01`…`CLS-06`, `CLS-09`, `CLS-10`, `POR-11`), and what it still has to add. Every
seam is read through `abacus.modules.closes.api` only; no epic queries the closes tables.

## C-02 (deliverables, adjustments, tax hand-off)
- **Ready:** `closes.api.close_for(tenant, work_item_id) -> CloseFacts` (status, period, plan version, reconciled count, open issues, attest); `register_status_guard(to_status, guard)` for `approved`, `delivered` and `locked` (fail closed: 409 `transition_not_available` until registered); accepted flux explanations for the commentary (CLS-10 c → CLS-08).
- **To add:** CLS-07 Adjustments (until then AJE-06 opens SHL-10, DV-6); CLS-04 b2/c Post AJE behind W1 for non-attest clients (DV-1); "Handoff to tax…" on CLS-02 (disabled with "Available after the December close locks").
- **Flags:** `closes.delivery`, `closes.tax_handoff`, `closes.gl_console` are C-02's.

## K-04 (boards)
- **Ready:** the close list and status vocabulary CLS-01 uses (four tiles; six statuses in the Status chip; QC-6, DF-23).
- **To add:** CLS-01 g/i and CLS-02 f/g Board views (DV-5); the close provider refuses every move, so CLS-01 h stays an accepted deviation until a close move dispatcher exists; SHL-21 for CLS-03 "Linked (n)".

## W-02 (workbench)
- **Ready:** the close's open issues and run status through `close_for`; CLS-02's composer hands off to the workbench.
- **To add:** a close context for workbench sessions (the composer's attachments), read through `closes.api`.

## W-03 (library agents)
- **Ready:** `close.agent` modes `intake`, `bank_rec`, `aje`, `flux`, `planner` (spec under `backend/src/abacus/modules/agents/specs/`), suite `evals/close_agent`; attribution "‹person› via Agent · Close Planner" (DV-4).
- **Not ready:** clearance per mode; a mode not cleared ships off with its template fallback (C-01 §10 item 5).

## I-01 (insights)
- **Ready:** `close_for` facts and the reconciled-accounts count for portfolio insights.
- **To add:** an insights read over close status history (not built ahead of its consumer).

## Flag retirement plan
`closes.engine`, `closes.portal_requests` and `closes.agent` (created 2026-11-14, expire 2027-05-13) retire in their own PR, held for the batch after the October 31 flip, or renew once with a dated retirement in C-02's window (C-01 §10 item 8). The retirement PR removes the flag checks, keeps the designed flag-off states only where an entitlement replaces them, and carries a written rollback (re-add the flag at its last value).

## Open at hand-off
- Real pilot firms: none (DEC-1391); the shadow runs on PF-X1 (DEC-1530).
- Pen-test delta for POR-11 and the close routes: deferred (DEC-1389).
- Downstream issues: one GitHub issue per epic above should link this note; not opened from this session (opening issues on the repo is the builder's call).
- Gaps carried: POR-11 d–g have no fixture scenario (docs/screens/POR-11.md); the C-01 §5.5 keyboard suites are not written (C-01-T50 log).
