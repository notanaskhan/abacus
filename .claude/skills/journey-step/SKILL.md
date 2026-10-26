---
name: journey-step
description: Add or turn on one step of an Accrued journey (J01–J28) end to end — the Brightwater Hale scenario event behind it, the exported fixture data, and the `journey.step` in the journey's spec with axe and the five invariants — or flip a `test.fixme` step to live when its screen and backend land. Use when a task's acceptance line names a journey step ("J04 pbc 3", "J02 step 5") or when a screen a journey walks reaches fixture or live.
---

# One journey step (F-04-T34; ADR-077)

The `journey-e2e` skill writes a journey's spec file; this one adds or turns on **one step** of
it. A step is one given-when-then line of the journey (blueprint §7): who acts, on which screen,
at which snapshot, and what the person then sees. A step is never skipped or deleted: an unbuilt
step stays `test.fixme` with its owner (ADR-079).

## Read first
- The journey's row in `docs/architecture/e2e-journeys.md` (spec path, first slice, gating epic).
- The step's line in `$ACCRUED_BLUEPRINT_DIR/accrued-blueprint/prompts/by-journey/Jnn-*.md` and
  blueprint §7; the screen contract `docs/screens/<ID>.md` for the artboard the step lands on.
- The harness (`apps/web/e2e/harness/index.ts`): `journey.as(persona, path, {clock})`,
  `journey.step(name, run, {outOfScope, probes, include})`. Personas: `harness/personas.ts`.

## Steps
1. **Place it.** Find the spec (`apps/web/e2e/journeys/Jnn-<slug>.spec.ts`) and the step's
   position. Name it `Jnn <slice> <k>: <person> <does what> (<SCREEN>)`; the inner
   `journey.step` is `Jnn <slice> step <k>: <what is on screen>`. Steps of one slice share one
   seeded tenant and one snapshot (`test.describe.serial` when a step depends on the one before).
2. **Data first.** The step reads only what the scenario holds at its snapshot
   (`backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/`, `epochs.py` for the
   instant). If the step needs a record the scenario lacks, add a timeline event in the owning
   area module: a deterministic `uuid5` id, an `at` on or before the snapshot, the acting person,
   and the owning module's `api.py` call (never a table insert, unless the area is bootstrapped
   and its comment says so). Names, figures and dates come from the handoff and blueprint §9,
   never invented. Then `make fixtures SNAPSHOT=<snapshot>` regenerates the exported JSON; never
   hand-edit it. Add a footing test for any figure the step asserts.
3. **Fixture side.** If the screen runs in fixture mode, the scenario for its artboard exists
   (`fixture-scenario` skill) and the step's persona and clock match the artboard's.
4. **Write the step.** Enter through `journey.as` only at the start of a test; inside, click or use
   `to.<ID>()`. Assert what the person sees by role and accessible name, with the copy verbatim
   from the screen contract. Wait on state, never on time. Give `probes` (API paths that must
   answer 404 to this persona: INV-3, INV-4) and `outOfScope` (names this persona must not see)
   whenever the step shows client data, a walled client is in the snapshot, or a portal persona
   acts. A step crossing a human gate also asserts the agent principal is refused (INV-1).
5. **Not walkable yet.** Keep it `test.fixme(title, owner("<epic> · <task> <what lands> · <sprint>, <chapter 01 date>"), body)`
   with the body written as it will run, so turning it on is deleting `.fixme`.
6. **Turn it on** when its screen is live (or fixture, for the fixture project) and its backend is
   merged: remove `.fixme` and the owner annotation in the same PR as the last piece that makes it
   walkable.
7. **Run** `make journeys JOURNEY_ARGS="e2e/journeys/Jnn-<slug>.spec.ts"` (fixture). For the full
   stack, `make dev`, `make seed-demo SNAPSHOT=<snapshot>` (plus the journey's holdouts and slices),
   then `make journeys-full JOURNEY_ARGS=…`. Never against a hosted database.
8. **Record.** The first spec for a journey changes its `Status` in `e2e-journeys.md` from
   `no spec` to `spec`. Walkability and last green runs go to the weekly quality report, not to
   the doc (a green night costs no commit). Append to the task's progress log.

## Never
Skip a step, delete one, or weaken an invariant to make it pass; assert on pixels (parity is
separate); let the agent persona use a human-only action except to assert that it is refused;
show the product's name on a portal step (INV-4); read real client data (ADR-085).
