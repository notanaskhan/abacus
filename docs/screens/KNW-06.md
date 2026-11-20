# KNW-06 · Engagement template builder — BH Audit Methodology · FS v6 (draft)

| Field | Value |
|---|---|
| Route and params | /knowledge/templates/$templateId/versions/$versionId/edit |
| Template and host frame | T2 (rail 330 · canvas 696 · dock 330) + 34 px draft banner; T18 read-only in preview |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/KNW-06 Engagement template builder - BH Audit Methodology - FS v6 -draf/` |
| Epic and tasks | K-03 · SPEC-720; K-03-T04 (TASK-8803); stubs K-03-T08/T09; build per `docs/plan/epics/K-03.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (K-03 §5.5). Copy keys live in `apps/web/src/screens/KNW-06/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures`, never hand-written.

## States
| Letter | Artboard | Persona | Clock (CT) | Figures that must foot | Build | Owner |
|---|---|---|---|---|---|---|
| a | Drafting | Margaret Okonkwo | Thu Oct 1, 9:10 AM | Thu Oct 1, 9:10 AM · Margaret Okonkwo · Program BH-FS | planned | AY |
| b | Preview mode | Margaret Okonkwo | Thu Oct 1, 9:10 AM | As a new FS audit · group · Group scoping sheet | planned | AY |
| c | Checks failing | Margaret Okonkwo | Thu Oct 1, 9:10 AM | After an edit to Group scoping · Publish blocked | planned | AY |
| d | Request list | Margaret Okonkwo | Thu Oct 1, 9:10 AM | 41 carried + 6 by rule | planned | AY |
| e | Triggers | Margaret Okonkwo | Thu Oct 1, 9:10 AM | The 2 template defaults | planned | AY |
| f | Another viewer | Hannah Leclerc | Thu Oct 1, 9:10 AM | Hannah Leclerc · comment, not edit | planned | AY |

## AVOID
gradients in product UI, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, the words Accrual/Arc/ACME/LSA, Fieldguide and its product names (Field Board, Field Auditor, Field Planner, Field Reviewer, Field Financials, Field Orchestrator, AI Actions, Prompt Library, Agent Knowledge), "task" for a to-do, the agent approving/signing/sending anything, a blue info banner, the reference's banner wording, editing controls visible in preview, publishing while checks fail, licensed content-pack text (paraphrase only), changes that reach live engagements from this screen.

## Deviations (chosen truth)
- Program steps are edited in KNW-03 (K-01); the builder links there. Skill cells show pins; the KNW-11 editor is K-05.
- **DF-34 times:** skill BH-SK-430 v2 is published at 9:34 AM, before FS v6 at 9:38 AM; any artboard showing the reverse is wrong. Truth: 9:34 then 9:38.
- Icon substitutes for layout-template and git-branch (K-03-T05, `icons.md`).
- Icon map: `docs/design/revisions/K-03-T05/icons.md` (`layout-template` → LayoutGrid, `git-branch` → GitFork).

## Walls and agent
- Walled users: 404, absent from lists, no hidden counts (INV-3, DEC-43).
- The agent never publishes, applies, holds, adopts, signs or raises an exception here (INV-1); attribution "‹person› via Agent" (INV-5).
