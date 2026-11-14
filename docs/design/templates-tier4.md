# Tier-4 templates: T4, T13, T14, T17 (F-07 close-out)

F-07-T23 (TASK-7956). What a session needs to build a screen on the tier-4 templates from the
handoff, and the notes each consumer epic picks up. Kits live in `packages/ui`; specimens are
registered in `packages/ui/src/specimens/index.ts`; the decisions are
`packages/ui/src/tokens/DECISIONS.md` ("Tier-4 kickoff" and "Tier-4 close-out").

## The four templates

| Template | Kit | Specimens | Locks | Consumers |
|---|---|---|---|---|
| T4 Workbench chat | `WorkbenchLayout`, `SessionList`, `ChatHeader`, `ChatThread` (slots `plan`, `question`, `approval`, `decision_ref`, `run_card`; `onEditResend`, `composerDisabledReason`), `QuestionCard`, `EmptySession`, `ContextPicker` | T4 a–f, TPL-04 a–e | Tier D, Tier B (TPL-04), axe, keyboard (F-07-T09) | W-02 (WB-01, WB-02, WB-03), W-03 (WB-07, WB-12), I-02 (the Today session) |
| T13 Calendar | `CalendarLayout`, `MonthGrid`, week and list views | TPL-13 a, a′, b–f | Tier D, Tier B, axe incl. the day popover, MonthGrid keyboard (F-07-T22) | T-08 (deadlines), K-04 (board), A-11 |
| T14 Graph canvas | `GraphCanvasLayout`, `GraphCanvas` (hand-rolled layered layout) | TPL-14 a–f | Tier D, Tier B, axe, graph keyboard | T-08 (relationships), A-11 |
| T17 Form renderer | `FormRendererLayout` on the E5 `SourceViewer` | TPL-17 a–f (F-07-T15's rendered faces and manifest) | Tier D, Tier B with the page body masked, axe, thumbnails keyboard | T-06 (TAX-11 form preview), TXP screens |

## Rules that bind every consumer
1. Data in, intents out: the kits never fetch, filter, sum or compute a date or a figure.
2. Every agent string goes through `AgentText` or `AgentBlocks`; a notice's words are the
   consumer's fixed copy for the server's code, never model text.
3. No Approve, Reject, Decide, Sign off, Release or Send control on an agent-owned surface; the
   consumer's slot draws P-04's cards for a person.
4. A locked or walled record draws nothing of its content (INV-3).
5. The draft watermark on a rendered form is inside the server's page image (DEC-78); the kit
   never draws or removes one.

## Hand-off notes
- **W-02** (Workbench): WB-01's thread is `ChatThread` on the session snapshot; context and drill
  items are left out of the thread; notices map codes to fixed words; WB-03's plan item is the
  PlanCard slot on `GET /v1/agent-runs/{id}/plan` (W-02-T21). Saved prompts are W-03's slot.
- **T-06** (entity depth): the T17 form face reads the contract request
  `docs/contracts/requests/t06-form-pages.md` (pages, manifest, K-1 rows, the tie state).
- **T-08** (deadlines and relationships): T13 and T14 read the requests
  `docs/contracts/requests/t08-deadlines.md` and `t08-relationships.md`.
- **W-03** (agent library): WB-07 and WB-12 plug into T4's `run_card` slot and the composer's
  draft; no new T4 prop.
- **K-04** (board): T13's MonthGrid takes board items through the deadline read model's shape;
  no retrofit of earlier date pickers (§11 R10).
- **A-11** (attest): T14 shows control relationships with the same node and edge kinds; a new
  kind is a kit change with its own specimen.
