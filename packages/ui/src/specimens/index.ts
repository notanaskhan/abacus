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
import { MenuSpecimen, TooltipSpecimen } from "./menus";
import { Overview } from "./overview";
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
];

export function specimenById(id: string): Specimen | undefined {
  return SPECIMENS.find((s) => s.id === id);
}
