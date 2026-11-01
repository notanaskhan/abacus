---
id: RB-46
title: Sampler and TB mapping — re-perform a sample, flips and rollback, retirement
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-09-17
---
# RB-46 · Sampler and TB mapping: re-perform a sample, flips and rollback, retirement

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | A sample that does not re-perform from its record: SEV2 (stop sampling for the firm). A mapping that reads stale when nothing changed, or not stale when it did: SEV3. Anything visible across firms: SEV1, go to RB-08 |
| Linked from | AUD-11 (a draw that failed), AUD-31 ("Changed after sign-off"), the incident register |
| SLO affected | none |
| Kill switches that apply | `sampling.sample_sets` and `ledger.tb_mapping` (per firm; ADR-089) |
| Rehearse by | Fri Sep 17, 2027, on staging with the synthetic test firm PF-X1 (Brightwater Hale; DEC-1530), before the Sep 21 flip |
| Last rehearsed | never |
| Last reviewed against an incident | never |

## A. Re-perform a sample from its record (ADR-340 §5; A-03 §4.4)
A version's record holds everything the draw used. Nothing is re-drawn in the product: this is a
check, run beside it.
1. **Read the record.** As a person on the engagement, `GET /v1/sample-sets/{id}?version=<n>`:
   `engine_version` (2.3), `seed` (24 bits, `seed_source` server), `population_sha256`, the
   method and parameters, the strata, `inputs_hash` and `items_hash`.
2. **Read the population.** `GET /v1/populations/{pid}`: the census or ledger source, its record
   count, total and SHA-256. The SHA-256 must equal the version's `population_sha256`. Otherwise
   stop: the population moved and the sample cannot be re-performed (SEV2).
3. **Re-perform.** On a clean checkout at the merge that drew it, in `uv run python`:
   - `compute.canonical.canonical(records)` over the population's records (exported from AUD-11's
     Open in Excel), whose hash must equal step 2's;
   - `compute.versions.sampler("2.3").select(...)`, with the recorded method, seed, size and strata.
   The draw's `inputs_hash` and `items_hash` must equal the record's, and its item keys must come
   out in the same order. The sampler is pure and frozen (ADR-340 §3), so nothing else is needed.
4. **Record.** Add the date, the engagement (by opaque reference) and the two hashes to the
   rehearsal log below. A mismatch is a SEV2 incident: turn `sampling.sample_sets` off for the firm
   (C) and open a review (ADR-097).

## B. Stale mapping
1. **Recognise:** AUD-31 shows "Changed after sign-off" after a TB version, or a signer reports a
   notice (`mapping_set_stale`) they did not expect.
2. **Check it is real.** Compare the newest sign-off's `content_hash` with the mapping view's
   current `content_hash` (`GET /v1/mapping-sets/{id}`). Equal hashes with a stale chip is a defect
   (SEV3): keep the flag on and file it. Different hashes are correct: a person re-confirms.
3. **Never re-sign for anyone.** Re-confirming is the preparer's own act (SHL-12, L1); the
   platform never moves a sign-off.

## C. Flips and rollback (freeze rule 3; DEC-68, P-29)
Each flip runs in a Tuesday 19:00 CT window with both founders. Before it:
- The journey e2e passes on staging (A-03-T19).
- A shadow run is done.
- This rollback is read aloud.

A production flip is a reviewed ops request, `deploy/production/ops-requests/flip-<date>-<pilot>.yaml`. Its `flip-precheck` checks the journeys, the shadow run, and that the approver is not the operator (`abacus_tools.flip_request`). The `rollback` field of that request points to this section.

Real-firm flips wait for a live pilot firm (DEC-1391). Until then, PF-X1 takes each flip and reports it as synthetic.

| Flag | Flip | Precondition | Rollback |
|---|---|---|---|
| `sampling.sample_sets` | **Tue Sep 21, 2027, 19:00 CT**, per firm | The CPA has signed `docs/quality/golden-reviews/sampling@2.3.md` | Turn the flag off for the firm (`make flag FIRM=<tenant> FLAG=sampling.sample_sets VALUE=false OPERATOR=<name> REASON=<text>`). Routes answer 404 and AUD-11 shows its C-20 state. Drawn versions, items and item requests stay; they are insert-only history. |
| `ledger.tb_mapping` | **Tue Oct 19, 2027, 19:00 CT**, per firm, for Dec-YE planning (A-04) | A-03-T19's j04 2 passes on staging | Turn the flag off for the firm. The mapping routes answer 404, the `trial_balance.version_created` subscriber does nothing, and the SPEC-316 v0 reads stay. Sign-offs and edits stay. |

Both flags expire Wed Apr 28, 2027 (DEC-137 override), before these dates. Renew both in the expiry wave (RB-26) with these flip dates, or the flip has no flag to turn on.

## D. Retirement (Thu Oct 21, 2027 batch)
Once every live firm has flipped, remove both flags in the Oct 21 batch:
- `docs/architecture/feature-flags/sampling.yaml` and `assurance.yaml`, then `make regenerate`.
- The `flag_enabled` checks in `sampling/contract.py`, `ledger` and `assurance/mapping.py`.
- The C-20 "not turned on" states of AUD-11 and AUD-31.

A firm that has not flipped by then keeps the flag, and its retirement moves to the next batch (a dated line here).

## Rehearsal log
| Date | Where | What | Result |
|---|---|---|---|
| — | — | — | — |
