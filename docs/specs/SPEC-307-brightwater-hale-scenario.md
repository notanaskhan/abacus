---
id: SPEC-307
title: "The Brightwater Hale scenario: content model, epochs and slices, holdouts, reserved ranges, the sink rule, the golden list, the business clock and fixture mode"
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-143, ADR-085]
related_specs: [SPEC-001, SPEC-306]
created: 2026-10-21
updated: 2026-10-21
---

## 1. Summary
F-04-T01. There is one synthetic firm, Brightwater Hale LLP, in two forms: a typed TS seed now (F-04-T05), and a Python scenario replayed through the service APIs later (F-04-T10 and T13).
- **Clock.** One business clock serves server and browser (`abacus.kernel.clock`, `apps/web/src/app-core/clock.tsx`). It stands at the demo instant, **Mon 14 Sep 2026, 9:24 AM CT**, on synthetic tenants, and is refused in production (ADR-143).
- **Fixture mode.** `apps/web/src/app-core/fixture-mode.ts` renders a real screen from a scenario, without a backend.

The canonical content (people, clients, engagements, figures) comes verbatim from the blueprint §9 seed and the handoff screens. Nothing is invented here.

## 2. Acceptance criteria
- **AC-1 Content model (E0).**
  - The firm is "Brightwater Hale LLP" with offices Chicago HQ, Denver and New York.
  - It has 46 of 46 seats: 14 named and 32 generator seat holders, counted 22 / 14 / 10 by office.
  - It has 184 clients: 16 named (§9.3), 66 roster clients (§9.7), and about 102 deterministic filler clients that never reuse a canonical surname.
  - There are 27 audits and assurance engagements: EBP 14 · FS 6 · Review 4 · Compilation and preparation 3. Their stages are 7 / 9 / 6 / 2 / 3 (Planning · Fieldwork · In review · Ready to release · Released), in C2 codes.
  - Northwind's PBC list reads 11 of 24, and Granite Peak's FS PBC list has 41 requests.
  - `firms.synthetic = true`, and no scenario name carries " (Synthetic)" (SPEC-001 AC-14 is amended for scenario entities only).
- **AC-2 Epochs and slices.**
  - **Named snapshots** (`epochs.py`): E0; Sep 24; Oct 1; Oct 6 11:20; Oct 21 14:10; Oct 26 16:15; Oct 27; Nov 9; Nov 13; Nov 16; Jan 11, 2027. Each screen contract names its snapshot, and loading a snapshot replays every event dated up to it.
  - **Slices** are the subsets a screen family needs (the E0 audit-core slice, the portal minimum).
- **AC-3 Holdouts.** `--holdout fairhaven_ebp` leaves out the Fairhaven Foods 401(k) client and its EBP engagement, so J02-audit-core creates them: CLI-01 shows 183 clients before and 184 after. `--holdout copperleaf` does the same for the CAS path.
- **AC-4 Reserved ranges.**
  - EINs use the `00-` prefix.
  - SSNs and ITINs use invalid ranges (000-, 666- or 9xx-), and are shown masked.
  - Phone numbers are 555-01xx.
  - `secrets_scan` and the ADR-085 identifier scan pass.
- **AC-5 The sink rule.** Every mailbox either is on the synthetic sink domain, or is shown as `@brightwaterhale.com` with delivery always rewritten to the sink.
- **AC-6 The golden list.** Seed footing tests assert the canonical figures above. A contamination lint (F-04-T09, DF-35, L10) fails on kit sample data and on variant spellings of canonical constants.
- **AC-7 The business clock (F-04-T02, T03).**
  - **Server time order:** `kernel.clock.now(tenant)` reads a `frozen(at)` block first, then the tenant demo clock (synthetic firms only, F-04-T07), then `ABACUS_DEMO_CLOCK` (local and staging), then real time. `system_now()` is always real and is used for security windows.
  - **Production refusal:** the API, worker and migration job refuse to start in production with a demo clock set.
  - **Browser time order:** `useNow()` reads the scenario clock first, then `?clock=` (dev, fixture and preview builds), then the server offset, then device time. `useToday()` is the Central business date, in CDT or CST.
- **AC-8 Fixture mode (F-04-T04).**
  - Handlers are keyed by OpenAPI path, and `defineScenarios()` is keyed by artboard state, each with a persona (`?as=`) and a clock.
  - `?latency=` slows every answer, and `never()` holds the loading state.
  - The production `dist/` holds no fixture strings.

## 3. Out of scope here
- The TS seed's rows (F-04-T05). They need the handoff and blueprint seed sources, which aren't on this machine, so they wait for those files.
- The Python scenario package and loader (F-04-T10, T13).
- Database business time (F-04-T06), the tenant demo-clock service (F-04-T07), and clock adoption at call sites (F-04-T11, T16).
