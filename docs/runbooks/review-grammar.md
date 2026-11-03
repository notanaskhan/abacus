# Review grammar: stale storms, projector rebuild, undo-window incidents, grant voids

**Owner:** the builder (solo; AMENDMENT-solo) · **Module:** `review` (P-04), with `agents` for
proposals and grants · **Severity:** SEV-3 by default; SEV-2 when a client-visible effect was
delivered after an undo, or a gate reads met while its owner says otherwise · **Last reviewed
against an incident:** never · **Task:** P-04-T61 (TASK-3222)

The review grammar is four records the owners never write themselves: sign-offs (`review.sign_offs`),
decisions (`review.decisions`), human gates (`human_gates`, a projection) and the approval grants
a proposal decision holds (`agents`). Each section below is one incident shape. All commands run
as an ECS one-off task on staging or production, never from a laptop against a hosted database.

## 1. Detect

| Signal | Where | Means |
|---|---|---|
| `sign_offs.went_stale` with `announced` above 50 in one relay cycle | logs, `review.stale_sign_offs` | a stale storm (§3) |
| Notification `sign_off_stale` volume spikes for one engagement | NOT-xx counts | the same storm, seen by signers |
| `human_gates.rebuilt` never logged after a release that changed a gate source | logs | the projection is behind its owners (§4) |
| A gate row reads `open` and its owner's facts say met (or the reverse) | `GET /v1/human-gates` against the owner's screen | projection drift (§4) |
| 409 `undo_window_closed` reported by a person who pressed Undo inside 10 seconds | support, `proposal.undone` absent | an undo-window incident (§5) |
| 409 `effect_started` on undo | API logs | the held effect already ran (§5) |
| A client-visible effect (portal message, request, envelope) delivered after `proposal.undone` | outbox, audit trail | a grant void failed (§6), SEV-2 |

## 2. Contain

- **Stale storm:** nothing to switch off: staleness is a query (`content_hash <> target hash`),
  and the detector only announces. If the notification volume itself is the harm, pause the
  `sign_off_stale` notification kind (RB-31), never the detector.
- **Projection drift:** gates are a projection; the owner's record is the truth. Tell the people
  waiting on the engagement to act from the owner's screen until §4 has run.
- **Undo incidents:** none needed for a closed window; a person decides again.
- **Grant void failure:** set `review.approve_agent_output` off for the firm (flag override,
  `docs/architecture/feature-flags/review.yaml`) so no new held effect is granted while you look.

## 3. Stale storms

A stale storm is many sign-offs going stale at once: a trial balance re-import, a mapping-set
version, a bulk workpaper refresh or an attribute-test grid edited row after row.

1. Find the change event that started it: `STALE_SOURCES` in `review/stale.py` names every event
   the detector consumes and the payload key that names the target.
2. Confirm it is real: each announced sign-off has `content_hash` unlike the target's hash now
   (`review.service.stale_of`). A real storm needs no repair: signers re-sign, and a re-sign is a
   new row.
3. Confirm it is once per sign-off: the announcement's event id is `went_stale_id(sign_off_id)`,
   so a replayed change event writes nothing new (IntegrityError skipped). A second notification
   for the same sign-off is a bug: open a SEV-3 with the sign-off id (identifiers only).
4. If an owner's hash changed when its content did not (a formatting or ordering change in the
   reviewable facts), the storm is false. Fix the owner's `register_reviewable_facts` provider so
   the hash covers only what the sign-off approves; existing stale rows stay as recorded (a
   sign-off row never changes), and the signers re-sign once.

## 4. Projector rebuild

`human_gates` is rebuildable from the owners' records (C13, DEC-320).

1. Run, per firm: `python -m abacus_tools.reproject_human_gates <tenant-id>`. It imports every
   module's `api` (as the worker does), reconciles every registered gate source over every
   engagement inside that firm's row-level security as the system, and logs `human_gates.rebuilt`
   with the rows written.
2. It is idempotent: a second run writes nothing, and right rows keep their `updated_at`.
3. A voided row stays voided. A row whose source no longer answers is closed, never deleted.
4. Run it after any release that adds a projected column or changes a gate source, and after an
   office change (which emits no C13 event yet).
5. If the second run still writes rows, a source's facts are unstable: compare two runs' row ids
   and open a SEV-3 against the source's owner module.

## 5. Undo-window incidents

`POST /v1/proposals/{id}/undo` (P-04-T29, DEC-713) is allowed only to the person who decided,
within 10 seconds on `kernel.clock`, while it is the proposal's latest decision.

1. 409 `undo_window_closed` after a person says they pressed inside 10 seconds: compare the
   decision's `decided_at` with the undo request's arrival in the API log. Network delay counts
   against the window; the window is not extended for anyone (DEC-24).
2. The remedy is a new decision, never a database edit: the person rejects, or a reviewer sends
   the work back. Record the incident in the rehearsal log below if it repeats.
3. 409 `effect_started`: the approval wrote field values someone has changed since, was applied
   by an owner's change-set applier, filed an evidence version (`inbox_match`), or its held
   effect consumed its grant. Nothing generic puts it back: the owner's screen reverses it as a
   new change.

## 6. Grant voids

An approval of agent output that has a client-visible effect holds a grant; the effect runs only
by consuming it. Undo voids the grant in the same unit of work as the `undone` decision.

1. A delivered effect after `proposal.undone` means the consumer did not check the grant: find
   the effect's outbox event and the grant id it carried.
2. Contain (§2), then tell the firm's engagement partner which client saw what (identifiers in
   the ticket, content only in the firm's own screens). RB-27 sets the clock if firm data left
   the firm.
3. Fix the consumer to consume the grant atomically with the effect; add a test that an undone
   proposal's effect is refused.

## 7. Verify

- Stale storm: `went_stale` count for the event equals the newest-per-level sign-offs that no
  longer match; a replay of the event writes zero.
- Rebuild: a second `reproject_human_gates` run writes zero rows.
- Grant void: the consumer test refuses an undone proposal's effect; the flag override is removed.

## 8. Review

Open the blameless review. Each action becomes a test, a lint rule, an alert or an ADR.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
| — | staging walk-through (pending) | Not rehearsed yet: the acceptance's staging rehearsal waits on the next staging deploy (batch close) | — |
