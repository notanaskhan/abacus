# F-07 tier 4: consumer-state coverage and handoff conflicts (F-07-T24)

TASK-7629 · DEC-4624 · Thu Nov 12, 2026. Binds SPEC-652 (the template props) to the consumer
screens that build on T4, T13, T14 and T17. Each artboard below maps to a kit prop or to a named
consumer slot. A consumer slot is a ReactNode or renderer the host passes in, so the kit never
draws it. Where an artboard has neither, an open DF row says so. Kit props are SPEC-652 AC-1 to
AC-6. "Host" means the consumer screen (W-02, T-08, T-06).

## T4 consumers: WB-01, WB-02, WB-03 (W-02)

| Artboard | State | Kit prop (template) | Consumer slot / host |
|---|---|---|---|
| WB-01a | Awaiting answer | `SessionRow.needs_answer` (amber dot) · `ChatThread.items` (`question`) → `QuestionCard` | — |
| WB-01b | Ask card step 2 | `QuestionCard {n, m, steps}` (AC-5) | — |
| WB-01c | Running 3 | `SessionRow.running` (spinner) · `SessionListProps.query` = filter | `run_card` slot (P-09 RunCard) |
| WB-01d | Scheduled run | `ChatThread.items` (`agent_blocks`, `artifact`) | `approval` slot (P-04 ApprovalCard, owner-only) |
| WB-01e | Failed | failed `tool_card` → `ChatErrorRow` · `onRetryStep`, `onOpenRun` | — |
| WB-01f | Search no results | `SessionListProps.query` → filtered-empty with Clear search | — |
| WB-01g | Locked thread | `SessionRow.locked` · `ChatThreadProps.locked` · `ChatHeaderProps.locked` (INV-3) | — |
| WB-01h | Load saved prompt | — | W-03 saved-prompts picker (`Composer` prefill through `onSend` draft); DF-43 below |
| WB-01i | Save to saved prompts | — | W-03 (WB-12); DF-43 below |
| WB-02a | Empty session | `ChatThread.items = []` (the empty prompt) · `Composer` | context chip: `ChatHeaderProps.context` |
| WB-02b | Picker · Documents | — | host O1 context picker (W-02-T09), result to `ChatHeaderProps.context` |
| WB-02c | Context loading | `ChatThread.items` (`notice`) | host skeleton cards in the context slot |
| WB-02d | Context attached | `ChatHeaderProps.context` (chips with ×) | — |
| WB-02e | Grounded answer | `agent_blocks` with citations (C4) · `notice` "Nothing was written." | — |
| WB-02f | Suggested prompt | `Composer` prefill (nothing sent) | host's suggested-prompt cards |
| WB-02g | Load saved prompt | — | W-03 (WB-12); DF-43 below |
| WB-02h | Saved prompt filled | `Composer` prefill | W-03 (WB-12); DF-43 below |
| WB-03a | Plan awaiting approval | — | `plan` slot (W-02 PlanCard) |
| WB-03a2 | Edit plan | — | `plan` slot (editable) |
| WB-03b | Gathering | `tool_card` rows (C2 `agent_run_step`) | `run_card` slot (progress) |
| WB-03c | Working | `agent_blocks` (`metric` parts) | `run_card` slot |
| WB-03d | Ready for review | `artifact` → `FileArtifactRow` · `onArtifact` | `approval` slot ("Save to Files") |
| WB-03d2 | O4 preview | `onArtifact(id, "open")` | host O4 preview (W-02 ArtifactPreview) |
| WB-03e | Approved | `notice` | `approval` slot (decided state, Undo 10 s) |
| WB-03f | Partial failure | failed `tool_card` · `onRetryStep` | `run_card` slot ("Prepared with 1 gap") |
| WB-03g | Cancelled at plan | `notice` "Plan cancelled by ‹person›" (formatActor) | `plan` slot (cancelled) |
| composed | DF-04, flag off, loading, error | `WorkbenchLayoutProps.viewState` (`restricted`, `flag-off`) | W-02-T22 boundary and §7216 rows |

## T13 consumer: HOME-03 (T-08)

| Artboard | State | Kit prop (`CalendarLayout`, AC-6; F-07-T10/T11) | Consumer slot / host |
|---|---|---|---|
| HOME-03a | Month | `view: "month"`, `month`, `today`, `chips[]` (tier from C2 `filing_deadline`) | — |
| HOME-03b | List | `view: "list"` (T1 IndexList with the Rule column) | — |
| HOME-03c | Week · Sep 13–19 | `view: "week"` (40 h rows, stage pill, initials) | — |
| HOME-03d | Person · Daniel Reyes | `onFilter` (Person chip); chips recomputed by the host's query | — |
| HOME-03e | Rule popover | `chips[].rule` (C21 rule text, DEC-76) → RulePopover (250 ms, on focus) | "Open return →" intent |
| HOME-03f | +9 more · Sep 15 | `onExpandDay` → day popover; "+n more" from computed fit | — |

## T14 consumer: CLI-03 (T-06; promoted from TPL-14, DEC-32, DF-02)

| Artboard (chapter 09 §9.6.1) | Kit prop (`GraphCanvasLayout`, AC-6) | Consumer slot / host |
|---|---|---|
| Graph with selection | `nodes`, `edges`, `selectedId`, `onSelect`, `onMove` (saved positions win) | 330 inspector: host `EntityInspector` (TIN reveal is P-12's logged path) |
| List view | `view: "list"` | — |
| Dependency banner | — | host banner (server-composed text: `at_risk` / `released`) |
| Add relationship… | — | host O3 writing `entity_relationships` |
| Walled node | omitted from `nodes` (DEC-43), no placeholder | — |
| External node | `nodes[].external` (dashed) | — |

## T17 consumer: TAX-11 (T-06)

| Artboard | State | Kit prop (`FormRendererLayout`, AC-6) | Consumer slot / host |
|---|---|---|---|
| TAX-11a | Page 1 | `pages[]` (server images), `selectedPage`, `schedules[]` | — |
| TAX-11b | K-1 · Jonah Feld | `pages[]` of the K-1 preview (watermark in the image) | K1List (host) |
| TAX-11c | Schedule K | `traces`, `onGoTo` | — |
| TAX-11d | Diagnostics clear | `schedules[].diagnostics = 0` | DiagnosticList (host) |
| TAX-11e | Loading | `pages = []` → skeleton thumbnails and page | — |

## Conflicts and their resolution

| # | Conflict | Resolution | Where recorded |
|---|---|---|---|
| 1 | T-board placeholder names. The T4 board's "bank download failed" and the T17 board's "Juno Okafor" and "Calder Family Trust" are not Brightwater Hale or Ridgeline people | Placeholders only: states are built from the TPL-04, TPL-13, TPL-14 and TPL-17 fixtures. T17a uses Jonah Feld and T17b Pell Street II LLC (§11 R5) | DECISIONS.md (F-07-T01 and this row) |
| 2 | Sep 15 counts. TPL-13a shows 3 chips and "+10 more"; HOME-03f shows "+9 more"; both are 13 items | Not a data conflict. Sep 15 holds 13 items (8 × 1065 + 3 × 1120-S + 2 envelopes). The "+n more" is computed from the cell's fit: 3 chips at 144 h, at most 4 (the AVOID rule). HOME-03f's taller cell fits 4, and the kit never hard-codes n | DECISIONS.md |
| 3 | TPL-14a viewer. The README says "Jonah Feld", a client persona on a firm screen | Olivia Brandt on every TPL-14 artboard (chapter 09 §9.6.1) | DECISIONS.md (F-07-T01) |
| 4 | TPL-17e and TAX-11b viewer. The README says "Jonah Feld" | Daniel Reyes on every TPL-17 artboard. TAX-11b's "Jonah Feld" names the K-1 recipient, not the viewer | DECISIONS.md |
| 5 | Watermark copy. The boards draw "PREVIEW", "Draft" and "Not for filing" variants | DEC-78's wording, "Draft — not for filing", drawn inside the server-rendered page image. The kit never draws or removes it (§11 R4) | DECISIONS.md |
| 6 | WB-01i has no letter in the spec's STATES list | Kept as an artboard (README note); it maps to W-03's saved-prompts flow | DF-43 (open) |
| 7 | Saved prompts (WB-01h/i, WB-02g/h) need a picker the T4 kit does not own | Consumer slot: W-03's WB-12 picker prefills the Composer. No kit prop is added | DF-43 (open; W-03) |

### Open DF row added

| DF | Item | Proposed resolution | Owner · due |
|---|---|---|---|
| DF-43 | Saved prompts inside the Workbench (WB-01h, WB-01i, WB-02g, WB-02h) | W-03's WB-12 picker opens from the Composer's "Saved prompts" control and prefills it; "Save to saved prompts" is a W-03 O3. The T4 kit gains no prop: the Composer takes a prefilled draft | AY · W-03 (S41) |
