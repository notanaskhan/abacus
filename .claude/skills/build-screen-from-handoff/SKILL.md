---
name: build-screen-from-handoff
description: Build or revise one Accrued screen by screen ID (for example AUD-03 or POR-03) from the Claude Design handoff — screen contract, route and manifest entry, a fixture scenario per artboard, L4/L3 code on existing templates and kits, tests from the revision acceptance checklist, axe and visual parity. Use for any task that implements or revises a screen ID.
---

# Build a screen from the handoff

## Paths that arrive later
If one of these is missing when this skill needs it, stop and report which one and the task that creates it.
- apps/web/src/routes/manifest/<module>.ts and apps/web/scripts/seed-manifest.mjs (arrive with F-04-T14, S3)
- docs/product/status-vocabulary.yaml (arrives with F-03-T04, S0). docs/product/decision-log.md arrives with F-02-T01 (S0); until then search docs/plan/09-decisions-adrs.md only, and create the log when you record a decision
- docs/design/HANDOFF_VERSION (arrives with F-05-T16, S1); kit and template specimens in packages/ui (F-05, S0–S10)
- routes/<surface>/<area>.tsx route files (arrive with F-03-T17, S1); apps/web/src/fixtures/contracts/ (P-08-T02, S4)
- e2e/screens/<ID>.spec.ts parity harness (arrives with P-08-T26, S9; the visual-parity harness itself with F-05)

Input: SCREEN_ID. Env: $ACCRUED_HANDOFF_DIR, $ACCRUED_BLUEPRINT_DIR (from .claude/settings.local.json).
The handoff is read-only and stays outside git. Copy into the repo only text you quote in the contract and copy files.

## 0. Preconditions — stop and report if one fails
- Search docs/product/decision-log.md and docs/plan/09-decisions-adrs.md for SCREEN_ID. An open decision is not a stop:
  decide it with the plan's proposed option, record it in docs/product/decision-log.md, and continue.
- apps/web/src/routes/manifest/<module>.ts has SCREEN_ID (else run `node apps/web/scripts/seed-manifest.mjs`).
- The template (T1–T22, O1–O6) and every kit in the README "Kits and components" have merged specimens in packages/ui
  (check /components). Missing → stop and propose a `ui-kit-component` task. Never build a kit inside a screen task.
- Endpoints exist in @abacus/api-client or a contract stub is merged. Otherwise draft types in
  apps/web/src/fixtures/contracts/ and record the gap, or build the stub first with the `api-contract` skill.
- The seed covers every lettered state's data (`fixture-scenario` skill). docs/design/HANDOFF_VERSION matches the local handoff.
- If the screen is POR-* or uses T7, T15 (portal) or T16, also follow the `portal-screen` skill.

## 1. Load, in this order (token-aware)
1. handoff/README.md lines 1–100 (once per session).
2. uploads/04-shared-context-block.md (+ 04b-addendum-context-block.md for wave ≥ 5 or later epochs).
3. handoff/screens/"<ID> <name>"/README.md — artboards (state, viewer, rendered), kits, links, deviations.
4. spec.md — measurements, copy, STATES, AVOID.
5. revision.md if present — CHANGES, NEW STATES, AVOID, Acceptance checklist. Revision wins for what it lists.
   Ignore spec-alt.md (identical to spec.md).
6. Only this screen's section of handoff/canvases/<canvas>.md (grep "## <ID>") — host frame, time notes.
7. For each mounted kit: its bundle in kit-handoffs/C-NN */ (README, specs) if one exists, else its kits.md section;
   design-tokens.md only for values missing from tokens.ts.
8. Status words from docs/product/status-vocabulary.yaml (blueprint §3.3.1) — never lib/status.js.
9. Screenshots: <ID>a.png and only the states the text leaves ambiguous; downscale first
   (`sips -Z 1440 in.png --out "$TMPDIR/x.png"`).
10. Only if behaviour is still unclear: the screen kit or the canvas method's renderVals() (grep), not the template.
Query screen-index.json with `python3 -I` one-liners; never print it whole.

## 2. Screen contract → docs/screens/<ID>.md (copy docs/screens/_TEMPLATE.md)
Route and params; template and host frame; persona and snapshot per artboard; each lettered state → the DATA condition
that produces it (never an `st` prop); API reads and writes with shapes and matrix actions; allowed_actions and read-only
reasons per role; status objects and codes; every copy string verbatim; every outbound link → manifest builder (planned
targets allowed); AVOID; acceptance bullets; figures that must foot; accepted deviations.
A contradiction between sources goes under "Open gaps" — never resolve it silently. If it changes the data model or copy,
take revision.md over spec.md over the blueprint, record the call in docs/product/decision-log.md, and continue.
If the task is amber (live data), write the plan into the task file now, then build.

## 3. Fixtures
screens/<ID>/scenarios.ts — one scenario per artboard letter: persona = viewer, clock = the state label's time (it wins over
`rendered`), snapshot. Names and numbers verbatim from the context block; never kit sample data. Loading = never();
error = 5xx handler; empty = a data condition, not a flag.

## 4. Build
- Route: lazy entry in routes/<surface>/<area>.tsx or an overlay registry entry; manifest status → fixture.
- screens/<ID>/index.tsx (L4) composes the template; data only via domain/<area> hooks (L3; add them there).
- copy.ts verbatim; <StatusPill object code>; format.ts for every number and date; AgentText/AgentProse for agent text;
  useGate + ?ov= overlays for human gates; useCan/allowed_actions; FeatureGate; to.<ID>() links; useNow() for time.
- Tokens only; Geist 400/500; no card borders; no literals. Portal: no "Accrued"; render at 1400, 720 and 390.

## 5. Tests
- <ID>.test.tsx: one test per artboard ("<ID>a default", …) plus loading, empty, error and not-allowed.
- Each revision.md acceptance bullet → a test named "<ID> acceptance: <bullet>"; each footing figure → a seed test.
- No agent-owned element exposes Approve, Sign off, Release, Send or Post; Reject… needs a reason; dialog openers end in "…".
- e2e/screens/<ID>.spec.ts: every scenario at 1440×900 DPR 2 in fixture mode; axe 0 serious or critical;
  parity against the handoff PNG — record the diff % per artboard in the contract.
- Write the acceptance tests before the screen code; never weaken one to get green.

## 6. Finish
make check-fast, then make check. Update the contract's deviations and the manifest status. Append to the task's Progress log.
Commit on a short branch and merge once make check is green. Optional: self-review with the reviewer subagents.

## Never
Invent data, states or screens; port kit sample data; edit generated files (packages/api-client/src/**, *.gen.ts, _matrix.py,
_flags.py); import firm shell code into portal code; render agent text raw;
let a click, drag, trigger or column sign off, approve, release, send or post; add a 14th nav item, a persona, a peer
benchmark or licensed publisher content (D1–D10, X-01…X-08).
