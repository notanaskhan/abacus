// An inline O3 sheet's keyboard contract (A-07-T48; S35 round 2 end pass): focus moves into the
// sheet when it opens, Tab and Shift+Tab stay inside it, Escape cancels, and focus returns to the
// control that opened it. For the frame-drawn sheets that cannot be the kit's portalled Dialog
// (the artboard draws them in place).
import { type RefObject, useEffect, useRef } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function useSheetFocus<T extends HTMLElement>(onEscape: () => void): RefObject<T | null> {
  const ref = useRef<T | null>(null);
  const escape = useRef(onEscape);
  escape.current = onEscape;
  // The opener, read once at the first render (StrictMode runs the effect twice in dev, and the
  // second run would otherwise take the sheet's own first control for the opener).
  const opener = useRef<HTMLElement | null | undefined>(undefined);
  if (opener.current === undefined) {
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  }
  useEffect(() => {
    const sheet = ref.current;
    if (sheet === null) return undefined;
    const items = (): HTMLElement[] => Array.from(sheet.querySelectorAll<HTMLElement>(FOCUSABLE));
    items()[0]?.focus();
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        e.preventDefault();
        escape.current();
        return;
      }
      if (e.key !== "Tab") return;
      const all = items();
      if (all.length === 0) return;
      const first = all[0];
      const last = all[all.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || !sheet.contains(active))) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && (active === last || !sheet.contains(active))) {
        e.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      opener.current?.focus();
    };
  }, []);
  return ref;
}
