# P-02 search flags: rollout, renewal and retirement

**Status: drafted (P-02-T14, DEC-4727).** The synthetic firms have `search.palette` on through the
Brightwater Hale scenario load (`loader.FLAGS_ON`): local, staging and the canary's firm. No real
firm is live (DEC-1391), so every real-firm step below is planned, not scheduled.

## Flags
Both are owned by `notanaskhan`, default off, rollout-only (P-28: no entitlement is involved) and
declared in `docs/architecture/feature-flags/platform.yaml`.

| Flag | Turns on | Expires | On where |
|---|---|---|---|
| `search.palette` | `POST /v1/search`, the recents routes, ⌘K and the SHL-02 mount (off: 404, Go… hidden) | 2027-05-07 | synthetic firms now; each real firm at onboarding |
| `search.agent_mode` | the `>` prefix (SHL-02 c) | 2027-05-07 | nowhere until W-02 ships WB-01's new-session target |

The indexer runs whatever the flags say, so a firm's index is warm before its flip.

## Before a real firm's flip
1. The S41 batch is deployed to staging and the canary: `shl-02-palette.spec.ts`, J13 step 4 and
   J16 steps 5 and 9 green on the full stack, axe at zero serious or critical.
2. The firm's index is full: `python -m abacus_tools.search reindex <tenant>` has completed
   (`search_index.reindex_completed`) and `drift <tenant>` answers 0 (RB-82).
3. The 1M load test has passed once on the current schema (`abacus_tools.loadtest.search`,
   first-group p95 ≤ 250 ms, relay lag p95 ≤ 5 s), with its numbers recorded in RB-82.
4. Outside the busy-season window (Jan 1 – Apr 20, P-29) or in the Tuesday slot with
   `flip_guard`'s approval (`make flag … --approved-by … --rollback "search.palette false"`).

**Flip:** `make flag FIRM=<tenant> FLAG=search.palette VALUE=true OPERATOR=<name> REASON=<text>`,
then one person at the firm opens ⌘K, searches a client and opens it.

**Rollback:** the same with `VALUE=false`. Nothing is lost: the index keeps running and Recent
keeps its rows; only the palette and routes go away (404).

## Renewal
Both flags are renewed in the monthly flag-hygiene batch while a real firm is still off. No expiry
may land in a freeze window: a renewal that would is pulled forward to the batch before it.

## Retirement (dated)
- **`search.palette`:** retired in the train of **Tue Apr 27, 2027**, the first train after the
  Jan 1 – Apr 20 window and before the 2027-05-07 expiry, once every live firm has it on. The
  retirement removes the flag check from the routes and the toolbar and deletes the declaration;
  if a live firm still has it off on Apr 20, the flag is renewed once and the retirement moves to
  the next train after that firm's flip.
- **`search.agent_mode`:** renewed until W-02's WB-01 target ships, then flipped per firm and
  retired on the same rule (the first train after every live firm has it), at the latest one
  renewal after W-02's last flip.
