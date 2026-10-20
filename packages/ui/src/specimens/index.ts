import type { ComponentType } from "react";
import { Overview } from "./overview";

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
];

export function specimenById(id: string): Specimen | undefined {
  return SPECIMENS.find((s) => s.id === id);
}
