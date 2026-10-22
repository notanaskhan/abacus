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
import { LedgerGridSpecimen, StatementGridSpecimen } from "./data";
import { MenuSpecimen, TooltipSpecimen } from "./menus";
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
