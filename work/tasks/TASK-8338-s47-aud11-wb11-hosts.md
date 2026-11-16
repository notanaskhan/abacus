---
id: TASK-8338
title: "S47 follow-up: live hosts for AUD-11 and WB-11 (link-contract rule 1)"
spec: SPEC-659
acceptance_criteria: [AC-20, AC-21, AC-22, AC-24]
risk_zone: amber
status: in-review
branch: s47-aud11-wb11-hosts
created: 2026-11-16
updated: 2026-11-16
---

## Objective
Spec section: SPEC-659 AC-20 to AC-24 (WB-11 detail), SPEC-657 (AUD-11 from AUD-12).
The S47 end pass (TASK-8337) left link-contract rule 1 red on AUD-12 → AUD-11 and ADM-08 →
WB-11: neither target had a live host (no route or `?ov=` overlay drew it). Build both hosts and
wire the two links.

## Plan
- AUD-11: `?ov=sampling:<workItemId>` (`ov.AUD11`), a full sheet drawing the same live canvas
  AUD-02 draws for `?section=sample_selection` (`SamplingLayer`); `@abacus/ui` exports the
  cockpit's canvas pane as `CockpitCanvasView` so the layer reuses it.
- WB-11: `GET /v1/integrations/{key}` implemented (`connect_detail.drawer` over WB-10's tile and
  the install it reads); `?ov=integration:<key>` (`ov.WB11`), the live O2 drawer
  (`WB-11/live.tsx`) with the connection card, read and never rows, recent events, agents using
  it, Reconnect… and Disconnect… (typed name, seen version) for a viewer holding the firm actions,
  "‹name› manages this firm connection." otherwise.
- Links: `AUD-12/links.ts` `samplingOverlay`, `ADM-08/links.ts` `integrationOverlay`.
- Tests: `WB-11/live.test.tsx`, `AUD-11/SamplingLayer.test.tsx`,
  `tests/integration/test_w01_wb11_drawer.py`; the C20 v2 stub list drops the detail route.
- Rollback: revert the one commit; the overlays are additive.

## Progress log
- 2026-11-16: built as above (DEC-5323). Link-contract rule 1 green; the new frontend and
  integration tests pass; C20 v2 contract, integrations unit and route-introspection suites pass.
  Partials (recorded in `docs/contracts/c20-integrations.md`): the catalogue carries no write,
  never or who-can-use copy for a firm app and no linked-returns count or mapping reference, so
  those WB-11 sections are not drawn yet; a dependent shows its capability key until the agents
  module registers names (W-01-T14's provider is not registered yet). AUD-11's Sign off… is not
  offered in the layer: the canvas hands the host a set id and version number, not the version
  id SHL-12 takes. The disconnect confirmation's second sentence ("Data already in Accrued is
  kept.") generalises the handoff's tax wording; check it with the WB-11 copy owner.
- 2026-11-16: found in passing: `test_w01t07_catalogue_import.py::test_the_app_reads_the_workbench_but_cannot_import`
  passed only after an earlier test in its file had imported `karbon` (red alone or on another
  xdist worker); it now imports its own row.
- 2026-11-16: gates. check-fast green (backend and frontend); web vitest 4,275 of 4,275, link
  contract rule 1 green. The first build put AUD-06's two route chunks 0.8 KB over the 140 KB
  budget: a second importer of AUD-11's canvas and the cockpit pane split both into shared
  chunks. The layer now imports them through AUD-02 (which re-exports them), so they stay in
  AUD-02's chunk (AUD-06 139.5 KB).
