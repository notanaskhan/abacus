import { AgentBlocksSpecimen } from "./agent-blocks";
import type { ComponentType } from "react";
import {
  ButtonSpecimen,
  CheckPillSpecimen,
  CountSpecimen,
  DoneCountSpecimen,
  IconButtonSpecimen,
  PillSpecimen,
  TagSpecimen,
} from "./controls";
import { FirmMarkSpecimen, MonogramSpecimen, PersonSpecimen, WordmarkSpecimen } from "./identity";
import { PulseSpecimen, RevealSpecimen, SpinnerSpecimen, TypingDotsSpecimen } from "./motion";
import {
  FieldsetSpecimen,
  FilterChipSpecimen,
  PickerSpecimen,
  SearchFieldSpecimen,
  ValueRowSpecimen,
} from "./inputs";
import {
  AccountTreeSpecimen,
  EvidenceGridSpecimen,
  LedgerGridSpecimen,
  StatementGridSpecimen,
  TallyStripSpecimen,
  VarianceSpecimen,
} from "./data";
import { AgentFilledSpecimen, AttributionSpecimen } from "./attribution";
import { GatesSpecimen } from "./gates";
import { MenuSpecimen, TooltipSpecimen } from "./menus";
import { IndexListSpecimen } from "./templates";
import { RailKitSpecimen, RecordCockpitSpecimen, RecordKitSpecimen } from "./record";
import {
  CitationChipSpecimen,
  CitationPopoverSpecimen,
  CiteMarkerSpecimen,
  MatchLightSpecimen,
  MatchWiredSpecimen,
} from "./cite";
import { PortalLayoutSpecimen } from "./portal";
import { T15Specimen, Tpl15Specimen } from "./auth";
import { T16Specimen } from "./signing";
import { RequestRowsSpecimen, T7Specimen, Tpl07Specimen } from "./requests";
import { ScreeningCardSpecimen } from "./screening";
import { NestedSplitSpecimen, SplitNarrowSpecimen, SplitPresetsSpecimen } from "./split";
import { ToastKindsSpecimen, ToastLiveSpecimen } from "./toasts";
import { Overview } from "./overview";
import {
  CommandPaletteSpecimen,
  ConfirmDialogSpecimen,
  DialogSpecimen,
  DrawerSpecimen,
  FullSheetSpecimen,
  OverlayStackingSpecimen,
  PopoverSpecimen,
  SheetModalSpecimen,
  WizardSpecimen,
} from "./overlays";
import {
  KpiTileSpecimen,
  ProgressBarSpecimen,
  RatioStatSpecimen,
  StatusTileSpecimen,
  StepCounterSpecimen,
  UploadRingSpecimen,
} from "./progress";
import {
  AgentRunningRowSpecimen,
  EmptyStateSpecimen,
  FlagOffStateSpecimen,
  ForcedStatesSpecimen,
  OfflineBannerSpecimen,
  RestrictedStateSpecimen,
  SkeletonSpecimen,
  ViewStateSpecimen,
} from "./states";
import {
  StatusDiscSpecimen,
  StatusMapSpecimen,
  StatusPillSpecimen,
  SubLineSpecimen,
  SyncChipSpecimen,
  TallyPillSpecimen,
  TickSpecimen,
} from "./status";
import {
  SegmentedGroupSpecimen,
  SegmentedSpecimen,
  SheetTabsSpecimen,
  UnderlineTabsSpecimen,
  ViewToggleSpecimen,
} from "./tabs";
import {
  AppShellSpecimen,
  PaneSpecimen,
  PortalToolbarSpecimen,
  RecordHeaderSpecimen,
  TabsbarSpecimen,
  TimelineSpecimen,
  ToolbarSpecimen,
} from "./shell";
import { CheckboxSpecimen, RadioSpecimen, ToggleSpecimen } from "./toggles";
import { Tpl18Specimen } from "./wizard";
import { T12Specimen, Tpl12Specimen } from "./settings";
import { T11Specimen, Tpl11Specimen } from "./dashboard";
import { SourceViewerSpecimen } from "./viewer";
import { Tpl02Specimen } from "./tpl02";
import { T3Specimen } from "./t3";
import { Tpl03Specimen } from "./tpl03";
import { T9Specimen } from "./t9";
import { T8Specimen } from "./t8";
import { Tpl08Specimen } from "./tpl08";
import { Tpl09Specimen } from "./tpl09";
import { T5Specimen, Tpl05Specimen } from "./t5";
import { FieldRowsSpecimen, GridSpecimen, LeadsheetSpecimen, VirtualGridSpecimen } from "./data-3";
import { SectionBandSpecimen, SourceDocsSpecimen, WorkpaperPaneSpecimen } from "./workpaper";

// The specimen registry behind the /components gallery (SPEC-048, F-05-T09). This entry is
// "@abacus/ui/specimens": only the gallery subtree, which a production build does not compile,
// imports it. Never re-export it from the package root.

export interface Specimen {
  /** Stable key, kebab-case, `<kit>-<name>` (C-00 ...); also the anchor on the index page. */
  id: string;
  /** The Component Sheet family or kit, as numbered in the handoff: "C-00". */
  kit: string;
  title: string;
  Component: ComponentType;
  /** `portal`: a client-portal surface. The white-label crawl (F-05-T39, INV-4) reads every one:
   * no product name outside the Secured by footer the firm turns on. */
  surface?: "portal";
}

export const SPECIMENS: readonly Specimen[] = [
  { id: "c-00-overview", kit: "C-00", title: "Components in use", Component: Overview },
  { id: "c-00-button", kit: "C-00", title: "Button", Component: ButtonSpecimen },
  { id: "c-00-icon-button", kit: "C-00", title: "IconButton", Component: IconButtonSpecimen },
  { id: "c-06-pill", kit: "C-06", title: "Pill", Component: PillSpecimen },
  { id: "c-06-count", kit: "C-06", title: "Count", Component: CountSpecimen },
  { id: "c-06-tag", kit: "C-06", title: "Tag", Component: TagSpecimen },
  { id: "c-06-done-count", kit: "C-06", title: "DoneCount", Component: DoneCountSpecimen },
  { id: "c-06-check-pill", kit: "C-06", title: "CheckPill", Component: CheckPillSpecimen },
  { id: "c-06-status-pill", kit: "C-06", title: "Status pills", Component: StatusPillSpecimen },
  { id: "c-06-status-disc", kit: "C-06", title: "Status discs", Component: StatusDiscSpecimen },
  { id: "c-06-subline", kit: "C-06", title: "Sub-lines", Component: SubLineSpecimen },
  { id: "c-06-sync-chip", kit: "C-06", title: "Sync chip", Component: SyncChipSpecimen },
  { id: "c-06-tick", kit: "C-06", title: "Ticks", Component: TickSpecimen },
  { id: "c-06-tally-pill", kit: "C-06", title: "Tally pills", Component: TallyPillSpecimen },
  { id: "c-06-status-map", kit: "C-06", title: "Status map", Component: StatusMapSpecimen },
  // T0 motion and identity (F-05-T14)
  { id: "c-20-spinner", kit: "C-20", title: "Spinners", Component: SpinnerSpecimen },
  { id: "c-20-pulse", kit: "C-20", title: "Pulse", Component: PulseSpecimen },
  { id: "c-10-reveal", kit: "C-10", title: "Reveal", Component: RevealSpecimen },
  { id: "c-10-typing-dots", kit: "C-10", title: "Typing dots", Component: TypingDotsSpecimen },
  { id: "fnd-01-wordmark", kit: "FND-01", title: "Wordmark", Component: WordmarkSpecimen },
  {
    id: "fnd-01-monogram",
    kit: "FND-01",
    title: "Monogram and Agent avatar",
    Component: MonogramSpecimen,
  },
  { id: "c-00-firm-mark", kit: "C-00", title: "Firm mark", Component: FirmMarkSpecimen },
  { id: "c-28-person", kit: "C-28", title: "People", Component: PersonSpecimen },
  // Inputs and tabs (F-05-T15)
  { id: "c-05-segmented", kit: "C-05", title: "Segmented", Component: SegmentedSpecimen },
  {
    id: "c-05-segmented-group",
    kit: "C-05",
    title: "SegmentedGroup",
    Component: SegmentedGroupSpecimen,
  },
  {
    id: "c-05-underline-tabs",
    kit: "C-05",
    title: "UnderlineTabs",
    Component: UnderlineTabsSpecimen,
  },
  { id: "c-05-sheet-tabs", kit: "C-05", title: "SheetTabs", Component: SheetTabsSpecimen },
  { id: "c-05-view-toggle", kit: "C-05", title: "ViewToggle", Component: ViewToggleSpecimen },
  { id: "f-search-field", kit: "F", title: "SearchField", Component: SearchFieldSpecimen },
  { id: "f-picker", kit: "F", title: "Picker", Component: PickerSpecimen },
  { id: "f-filter-chip", kit: "F", title: "FilterChip", Component: FilterChipSpecimen },
  { id: "f-toggle", kit: "F", title: "Toggle", Component: ToggleSpecimen },
  { id: "f-radio", kit: "F", title: "Radio", Component: RadioSpecimen },
  { id: "f-checkbox", kit: "F", title: "Checkbox", Component: CheckboxSpecimen },
  { id: "c-13-value-row", kit: "C-13", title: "ValueRow", Component: ValueRowSpecimen },
  { id: "c-13-fieldset", kit: "C-13", title: "Fieldset", Component: FieldsetSpecimen },
  { id: "c-00-menu", kit: "C-00", title: "Menu", Component: MenuSpecimen },
  { id: "c-00-tooltip", kit: "C-00", title: "Tooltip", Component: TooltipSpecimen },
  // Shell L1 (F-05-T18)
  { id: "c-00-toolbar", kit: "C-00", title: "Toolbar", Component: ToolbarSpecimen },
  {
    id: "c-00-portal-toolbar",
    kit: "C-00",
    title: "PortalToolbar",
    Component: PortalToolbarSpecimen,
    surface: "portal",
  },
  {
    id: "c-00-record-header",
    kit: "C-00",
    title: "RecordHeader",
    Component: RecordHeaderSpecimen,
  },
  { id: "c-00-tabsbar", kit: "C-00", title: "Tabsbar", Component: TabsbarSpecimen },
  { id: "c-00-pane", kit: "C-00", title: "Pane and PaneHeader", Component: PaneSpecimen },
  { id: "c-23-timeline", kit: "C-23", title: "Timeline", Component: TimelineSpecimen },
  { id: "c-00-app-shell", kit: "C-00", title: "AppShell", Component: AppShellSpecimen },
  // View states and feedback (F-05-T19): C-20 States kit and C-19 Progress kit
  { id: "c-20-view-states", kit: "C-20", title: "ViewState panes", Component: ViewStateSpecimen },
  {
    id: "c-20-forced-states",
    kit: "C-20",
    title: "Forced states",
    Component: ForcedStatesSpecimen,
  },
  { id: "c-20-empty-state", kit: "C-20", title: "EmptyState", Component: EmptyStateSpecimen },
  { id: "c-20-skeleton", kit: "C-20", title: "Skeleton", Component: SkeletonSpecimen },
  {
    id: "c-20-agent-running-row",
    kit: "C-20",
    title: "AgentRunningRow",
    Component: AgentRunningRowSpecimen,
  },
  {
    id: "c-20-offline-banner",
    kit: "C-20",
    title: "OfflineBanner and fieldset empty",
    Component: OfflineBannerSpecimen,
  },
  {
    id: "c-20-restricted",
    kit: "C-20",
    title: "Restricted state",
    Component: RestrictedStateSpecimen,
  },
  { id: "c-20-flag-off", kit: "C-20", title: "Flag-off state", Component: FlagOffStateSpecimen },
  { id: "c-19-progress-bar", kit: "C-19", title: "ProgressBar", Component: ProgressBarSpecimen },
  { id: "c-19-ratio-stat", kit: "C-19", title: "RatioStat", Component: RatioStatSpecimen },
  { id: "c-19-upload-ring", kit: "C-19", title: "UploadRing", Component: UploadRingSpecimen },
  { id: "c-19-step-counter", kit: "C-19", title: "StepCounter", Component: StepCounterSpecimen },
  { id: "c-19-kpi-tile", kit: "C-19", title: "KPI tile", Component: KpiTileSpecimen },
  { id: "c-19-status-tile", kit: "C-19", title: "StatusTile", Component: StatusTileSpecimen },
  // Attribution and human verbs (F-05-T30): C-31
  {
    id: "f05-attribution",
    kit: "H1",
    title: "Attribution and HumanAction",
    Component: AttributionSpecimen,
  },
  {
    id: "c-31-agent-filled",
    kit: "C-31",
    title: "AgentFilledMarker",
    Component: AgentFilledSpecimen,
  },
  // C-34 ScreeningCard (P-06-T22): flagged, passed, running and not screened
  {
    id: "c-34-screening-card",
    kit: "C-34",
    title: "ScreeningCard",
    Component: ScreeningCardSpecimen,
  },
  // Templates (F-05-T28): T1 Index list, artboards T1a to T1e
  { id: "t1-index-list", kit: "T1", title: "Index list", Component: IndexListSpecimen },
  // T2 RecordCockpit (F-05-T40): the C-03 Rail kit, the C-04 Record kit and artboards T2a to T2e
  { id: "c-03-rail", kit: "C-03", title: "RecordRail", Component: RailKitSpecimen },
  { id: "c-04-record", kit: "C-04", title: "Record kit", Component: RecordKitSpecimen },
  {
    id: "t2-record-cockpit",
    kit: "T2",
    title: "Record cockpit",
    Component: RecordCockpitSpecimen,
  },
  // C-02 Workpaper kit and the C-15 source-document rows (F-05-T50)
  { id: "c-02-section-band", kit: "C-02", title: "SectionBand", Component: SectionBandSpecimen },
  { id: "c-02-workpaper", kit: "C-02", title: "WorkpaperPane", Component: WorkpaperPaneSpecimen },
  {
    id: "c-15-source-docs",
    kit: "C-15",
    title: "Source documents",
    Component: SourceDocsSpecimen,
  },
  // T3 EvidenceTriad (F-05-T53): Review, Prepare and Two-pane presets, T3a to T3e
  { id: "t3-evidence-triad", kit: "T3", title: "Evidence triad", Component: T3Specimen },
  // T8 InboxLayout and the C-15/C-18 File kit (F-05-T56): T8a to T8e
  { id: "t8-inbox", kit: "T8", title: "Inbox master-detail", Component: T8Specimen },
  // T5 CatalogLayout with C-11 AgentCard and C-14 ConnectionTile (F-05-T59): T5a to T5f, TPL-05
  { id: "t5-catalog", kit: "T5", title: "Catalog grid", Component: T5Specimen },
  { id: "tpl-05", kit: "TPL-05", title: "Catalog grid specimen", Component: Tpl05Specimen },
  // T9 QueueDetailLayout and the C-17 Issue kit (F-05-T55): T9a to T9e
  { id: "t9-queue-detail", kit: "T9", title: "Queue · detail · evidence", Component: T9Specimen },
  // TPL-08 firm Inbox specimen, the Feld thread (F-05-T58): TPL-08a to TPL-08e
  { id: "tpl-08", kit: "TPL-08", title: "Inbox master-detail specimen", Component: Tpl08Specimen },
  // TPL-09 three-preset specimen on the seed's issue lists (F-05-T57): TPL-09a to TPL-09g
  {
    id: "tpl-09",
    kit: "TPL-09",
    title: "Queue · detail · evidence specimen",
    Component: Tpl09Specimen,
  },
  // TPL-03 Feld 1040 review specimen (F-05-T54): TPL-03a to TPL-03e
  { id: "tpl-03", kit: "TPL-03", title: "Evidence triad specimen", Component: Tpl03Specimen },
  // TPL-02 Northwind 401(k) cockpit specimen (F-05-T51): TPL-02a to TPL-02e
  { id: "tpl-02", kit: "TPL-02", title: "Record cockpit specimen", Component: Tpl02Specimen },
  // T7 PortalLayout (F-05-T35): split, reduced (T7g) and mobile (T7-M) with the bottom tab bar
  {
    id: "t7-portal-layout",
    kit: "T7",
    title: "Portal layout",
    Component: PortalLayoutSpecimen,
    surface: "portal",
  },
  // C-16 Request kit, portal variant (F-05-T36): row states, T7a to T7g and T7-M, TPL-07
  {
    id: "c-16-request-rows",
    kit: "C-16",
    title: "RequestRow",
    Component: RequestRowsSpecimen,
    surface: "portal",
  },
  {
    id: "t7-client-portal",
    kit: "T7",
    title: "Client portal",
    Component: T7Specimen,
    surface: "portal",
  },
  {
    id: "tpl-07",
    kit: "TPL-07",
    title: "Client portal specimen",
    Component: Tpl07Specimen,
    surface: "portal",
  },
  // T15 AuthCard (F-05-T37): T15a to T15c and TPL-15a to TPL-15j
  {
    id: "t15-auth-card",
    kit: "T15",
    title: "Auth card",
    Component: T15Specimen,
    surface: "portal",
  },
  {
    id: "tpl-15",
    kit: "TPL-15",
    title: "Auth card specimen",
    Component: Tpl15Specimen,
    surface: "portal",
  },
  // T16 SigningCeremony (F-06-T04): b and c; a is a Tier C screenshot (DF-12).
  {
    id: "t16-signing-ceremony",
    kit: "T16",
    title: "Signing ceremony",
    Component: T16Specimen,
    surface: "portal",
  },
  // SplitLayout (F-05-T29): C-09
  {
    id: "c-09-split-presets",
    kit: "C-09",
    title: "SplitLayout presets",
    Component: SplitPresetsSpecimen,
  },
  { id: "c-09-nested-split", kit: "C-09", title: "NestedSplit", Component: NestedSplitSpecimen },
  {
    id: "c-09-split-narrow",
    kit: "C-09",
    title: "SplitLayout at 1280",
    Component: SplitNarrowSpecimen,
  },
  // E4 DataTable engine (F-05-T27): C-01
  { id: "c-01-ledger", kit: "C-01", title: "Ledger grammar", Component: LedgerGridSpecimen },
  {
    id: "c-01-statement",
    kit: "C-01",
    title: "Statement grammar",
    Component: StatementGridSpecimen,
  },
  // P-09-T06: AgentBlocks v1 and AgentProse
  { id: "p-09-agent-blocks", kit: "P-09", title: "AgentBlocks", Component: AgentBlocksSpecimen },
  // E1 MatchProvider, E2 popover host and the C-07 Cite kit (F-05-T41)
  { id: "c-07-cite-marker", kit: "C-07", title: "CiteMarker", Component: CiteMarkerSpecimen },
  {
    id: "c-07-citation-popover",
    kit: "C-07",
    title: "CitationPopover",
    Component: CitationPopoverSpecimen,
  },
  {
    id: "c-07-citation-chip",
    kit: "C-07",
    title: "CitationChip",
    Component: CitationChipSpecimen,
  },
  {
    id: "c-07-wired",
    kit: "C-07",
    title: "Wired to MatchProvider",
    Component: MatchWiredSpecimen,
  },
  { id: "e1-match-light", kit: "E1", title: "Match light", Component: MatchLightSpecimen },
  // DataTable grammars 2 (F-05-T43): evidence, the variance cell, TallyStrip, AccountTree
  { id: "c-01-evidence", kit: "C-01", title: "Evidence grammar", Component: EvidenceGridSpecimen },
  { id: "c-01-variance", kit: "C-01", title: "Variance cell", Component: VarianceSpecimen },
  { id: "c-01-tally-strip", kit: "C-01", title: "TallyStrip", Component: TallyStripSpecimen },
  { id: "c-01-account-tree", kit: "C-01", title: "AccountTree", Component: AccountTreeSpecimen },
  // DataTable grammars 3 (F-05-T52): grid, leadsheet, field rows, virtualisation
  { id: "c-01-grid", kit: "C-01", title: "Grid grammar", Component: GridSpecimen },
  { id: "c-01-leadsheet", kit: "C-01", title: "Leadsheet grammar", Component: LeadsheetSpecimen },
  { id: "c-01-fields", kit: "C-01", title: "Field rows", Component: FieldRowsSpecimen },
  { id: "c-01-virtual", kit: "C-01", title: "Virtualisation", Component: VirtualGridSpecimen },
  // Toasts E3 (F-05-T21): C-21
  { id: "c-21-toast-kinds", kit: "C-21", title: "Toast kinds", Component: ToastKindsSpecimen },
  { id: "c-21-toast-live", kit: "C-21", title: "Toast live stack", Component: ToastLiveSpecimen },
  // Overlay stack E3 (F-05-T20): O1 to O6, the C-22 dialogs and the C-23 drawer
  { id: "o1-popover", kit: "O1", title: "Popover", Component: PopoverSpecimen },
  { id: "c-23-drawer", kit: "C-23", title: "Drawer", Component: DrawerSpecimen },
  { id: "o3-sheet-modal", kit: "O3", title: "SheetModal", Component: SheetModalSpecimen },
  { id: "o4-full-sheet", kit: "O4", title: "FullSheet", Component: FullSheetSpecimen },
  {
    id: "o5-command-palette",
    kit: "O5",
    title: "CommandPalette",
    Component: CommandPaletteSpecimen,
  },
  { id: "o6-wizard", kit: "O6", title: "Wizard", Component: WizardSpecimen },
  { id: "c-22-dialog", kit: "C-22", title: "Dialog", Component: DialogSpecimen },
  {
    id: "c-22-confirm-dialog",
    kit: "C-22",
    title: "ConfirmDialog",
    Component: ConfirmDialogSpecimen,
  },
  // E5 SourceViewer shell (F-05-T47): C-08, full and evidence variants, reveal slot, states
  {
    id: "c-08-source-viewer",
    kit: "C-08",
    title: "SourceViewer",
    Component: SourceViewerSpecimen,
  },
  // T11 DashboardLayout (F-05-T46): T11a to T11f and TPL-11a to TPL-11f
  { id: "t11-dashboard", kit: "T11", title: "Dashboard", Component: T11Specimen },
  { id: "tpl-11", kit: "TPL-11", title: "Dashboard specimen", Component: Tpl11Specimen },
  // T12 SettingsLayout (F-05-T45): T12a to T12d and TPL-12a to TPL-12e
  { id: "t12-settings", kit: "T12", title: "Settings form", Component: T12Specimen },
  { id: "tpl-12", kit: "TPL-12", title: "Settings form specimen", Component: Tpl12Specimen },
  // O6 wizard specimen (F-05-T38): TPL-18a to TPL-18e, the type catalogue and the gate cards
  { id: "tpl-18", kit: "TPL-18", title: "Stepper wizard specimen", Component: Tpl18Specimen },
  // E7 human gates (P-04-T40): ApprovalCard, SignOffSlots, DecisionCard, ChecksList
  { id: "e7-gates", kit: "E7", title: "Human gates", Component: GatesSpecimen },
  {
    id: "o1-o6-stacking",
    kit: "O1-O6",
    title: "Stacking and the OverlayStack",
    Component: OverlayStackingSpecimen,
  },
];

export function specimenById(id: string): Specimen | undefined {
  return SPECIMENS.find((s) => s.id === id);
}

// The seed names and figures specimens draw (F-05-T33), for the app's footing test.
export * as SPECIMEN_SEED from "./seed-figures";
// P-03-T07: the synthetic page images, for the C4 fixture handlers' page route.
export { FORM_PAGE_PNG, STATEMENT_PAGE_PNG } from "./viewer-pages";
export { TPL08_CLIENTS, type Tpl08Message, tpl08Messages } from "./tpl08-data";
