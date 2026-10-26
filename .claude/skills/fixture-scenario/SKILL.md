---
name: fixture-scenario
description: Add or extend the Brightwater Hale seed and the per-artboard fixture scenarios for a screen — typed with the generated API types, one scenario per artboard letter with persona, clock and snapshot, plus footing tests. Use before building a screen, when a contract stub lands, or when a screen needs new states.
---

# Fixture scenarios

## Paths
- The Python scenario (the one source, ADR-085): backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/
  (`epochs.py` holds the named snapshots; `make seed-demo SNAPSHOT=<snapshot>` loads it locally).
- Exported fixture JSON: `make fixtures SNAPSHOT=<snapshot>` writes one apps/web/src/fixtures/seed/<snapshot>.<read>.json
  per MVP read path, imported by `seed/exported.ts` (F-04-T31); the TS seed in apps/web/src/fixtures/seed/<area>.ts
  stays for paths not exported yet.
- kernel.clock, fixture mode and docs/product/status-vocabulary.yaml exist.

Input: SCREEN_ID or a contract name. Sources: $ACCRUED_HANDOFF_DIR/uploads/04-shared-context-block.md (+ 04b for waves ≥ 5),
blueprint §9 and addendum §9, the screen's README artboard table (state, viewer, rendered), docs/screens/<ID>.md.

## Precedence — stop on a contradiction and record it as an open gap
Shared context block > addendum block > blueprint §9 > kit and gallery sample data. Never port kit sample data
(Elena Ruiz, "Ridgeview Partners", 21 integrations, a 13-task close run, closes ending "Closed").
When an artboard's state label and its `rendered` date disagree, the state label wins.

## Steps
1. For each artboard letter: viewer → persona; state label or note → data condition; time → clock; epoch → snapshot
   (E0 = Mon 14 Sep 2026, 9:24 AM CT; E1; E2; dated snapshots).
2. Seed records in apps/web/src/fixtures/seed/<area>.ts with canonical-name constants, typed `satisfies <Generated>[]`.
   With no contract yet, use draft types in fixtures/contracts/<name>.ts (deleted when the stub lands).
   After F-04 exports the seed (`make fixtures`), change scenarios/brightwater_hale instead and regenerate.
3. Handlers in fixtures/handlers/<area>.ts match `METHOD /v1/path/{param}` templates; `?latency=` supported;
   loading = never(); error = a 5xx handler; empty = a data condition, not a flag.
4. screens/<ID>/scenarios.ts: defineScenarios(ID, { a: { label, persona, clock, snapshot, search?, override?, interact? }, … }).
   One per lettered artboard, plus sub-states (a2) and primes (b′) the README lists. Check missing letters against the
   spec's STATES and record them.
5. Footing: every figure the README or revision calls out becomes a test in fixtures/seed/__tests__/<area>.foot.test.ts,
   using format.ts and bigint decimals, never floats.
6. Walls and scopes: include the walled persona (Lena Park × Ashford) and the portal personas' scopes where the screen has them.
7. Run the area's and the screen's Vitest suites; make check-fast; append to the Progress log.

## Never
Invent names, figures or dates; use real people or firms; let fixture strings reach non-fixture code (CI greps the
production dist for "Brightwater", "Northwind" and "scenario"); hand-edit exported seed JSON.
