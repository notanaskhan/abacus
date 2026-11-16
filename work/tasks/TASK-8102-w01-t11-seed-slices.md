---
id: TASK-8102
title: W-01-T11 Brightwater Hale Connect seed slice, fixture parity and golden tests
spec: SPEC-659
acceptance_criteria: [AC-1, AC-2, AC-3, AC-6, AC-23]
risk_zone: green
status: in-review
branch: w01-t11-seed-slices
created: 2026-11-15
updated: 2026-11-15
---

## Objective
The synthetic tenant's Connect installs, so `make seed-demo` and fixture mode show the same WB-10 data.

## Built
- `integrations/synthetic.py`: `seed_synthetic_install`, `seed_synthetic_event` (synthetic environments and synthetic firms only; no secrets).
- Slice `connect` (`connect_slice.py`): the nine E0 installs (CCH as a file bridge per OQ-3, the four ledgers as firm apps, Box and Microsoft 365 Felix's, Box Hannah's), CCH's timeline Jan 14 to Sep 14 (DF-34) with the Aug 17 9:05 AM import as WB-11's snapshot; loader handlers; `make seed-demo` imports the catalogue first, as the operator would.
- Golden tests (`tests/unit/integrations/test_w01t11_connect_seed.py`): 53 = 9 + 38 + 6 at E0, 55 = 9 + 40 + 6 at E2, Felix's nine equal the fixture's, WB-10 d for Hannah, Workstream's reason, CCH file bridge. The W-01 AC suite's AC-1 now passes over HTTP with the slice's installs at E0.

## Partly built
- The 224-returns golden (WB-11's linked count) and the five-agents golden (dependents) need W-01-T14/T15's services (`requires_integrations`, the detail projection).
- Bluestem's Sage Intacct client connection: no Bluestem client person is named in the scenario to connect it; left for W-01-T15's client-companies list.
- `make seed-demo` was not run here (no local stack in this session).

## Progress log
- 2026-11-15: built; goldens and the AC suite green; stacked on #2101.
