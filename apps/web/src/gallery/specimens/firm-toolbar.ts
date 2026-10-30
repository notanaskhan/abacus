// The firm toolbar a specimen's window draws (F-06-T13, T14): the thirteen nav labels from the
// design system's scope guards and the session's firm, with an area lit. Static: a specimen never
// navigates (the app's own toolbar data lives in shell/, which specimens may not import).
import type { ToolbarProps } from "@abacus/ui";
import { nav } from "@abacus/ui/scope-guards.gen.json";

export function specimenToolbar(firm: string, active: string): ToolbarProps {
  return { nav: nav.map((label) => ({ label })), firm, active, unread: true };
}
