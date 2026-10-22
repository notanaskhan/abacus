import { useEffect, useRef } from "react";
import { type Area, areaByChord } from "../../app-core/nav-areas";

// The toolbar's keyboard (P-01-T02; SHL-01c; AC 1.1.7): G then H, T, A, C or W goes to that area,
// and ? opens the shortcuts. ⌘K and Ctrl K are AppShell's (it calls the toolbar's onGo). Nothing
// fires while focus is in a text field, or with a modifier held.

/** How long after G the second key still counts (ms). */
export const CHORD_MS = 1500;

/** True when the key belongs to a field: an input, textarea, select or contenteditable. */
export function inTextField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable || target.closest("[contenteditable='true']") !== null) return true;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export interface ChordHandlers {
  onArea: (area: Area) => void;
  onHelp: () => void;
}

export function useGoChords(enabled: boolean, handlers: ChordHandlers): void {
  const latest = useRef(handlers);
  useEffect(() => {
    latest.current = handlers;
  });
  useEffect(() => {
    if (!enabled) return undefined;
    let pendingSince: number | null = null;
    const onKey = (event: KeyboardEvent): void => {
      if (event.defaultPrevented || inTextField(event.target)) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "?") {
        pendingSince = null;
        event.preventDefault();
        latest.current.onHelp();
        return;
      }
      const now = event.timeStamp;
      if (pendingSince !== null && now - pendingSince <= CHORD_MS) {
        pendingSince = null;
        const area = areaByChord(key);
        if (area !== undefined) {
          event.preventDefault();
          latest.current.onArea(area);
        }
        return;
      }
      pendingSince = key === "g" && !event.shiftKey ? now : null;
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
    };
  }, [enabled]);
}
