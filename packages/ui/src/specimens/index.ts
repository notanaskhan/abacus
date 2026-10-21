import type { ComponentType } from "react";
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
  { id: "c-06-status-pill", kit: "C-06", title: "Status pills", Component: StatusPillSpecimen },
  { id: "c-06-status-disc", kit: "C-06", title: "Status discs", Component: StatusDiscSpecimen },
  { id: "c-06-subline", kit: "C-06", title: "Sub-lines", Component: SubLineSpecimen },
  { id: "c-06-sync-chip", kit: "C-06", title: "Sync chip", Component: SyncChipSpecimen },
  { id: "c-06-tick", kit: "C-06", title: "Ticks", Component: TickSpecimen },
  { id: "c-06-tally-pill", kit: "C-06", title: "Tally pills", Component: TallyPillSpecimen },
  { id: "c-06-status-map", kit: "C-06", title: "Status map", Component: StatusMapSpecimen },
];

export function specimenById(id: string): Specimen | undefined {
  return SPECIMENS.find((s) => s.id === id);
}
