// The named import keeps the rest of scope-guards (its banned-term table) out of the bundle.
import { nav } from "@abacus/ui/scope-guards.gen.json";

// The firm bar (F-02-T09; SHL-01; D4): exactly 13 areas, in chapter 04 section 2.2's order, from
// docs/architecture/scope-guards.yaml. An item has no badge or count: the bell shows a dot only.
export interface NavItem {
  label: string;
}

export const NAV: readonly NavItem[] = nav.map((label) => ({ label }));
