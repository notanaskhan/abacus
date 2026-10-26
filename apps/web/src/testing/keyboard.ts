// Keyboard helpers for the screen keyboard suites (P-06-T26; P-06 §5.6). jsdom does not move focus
// on Tab, so a suite reads the tab order from the DOM instead: every element a Tab can land on, in
// document order (no positive tabindex is used anywhere in the app, so document order is the
// order). Hidden, inert and disabled elements are left out, as the browser leaves them out.

const FOCUSABLE = [
  "a[href]",
  "button",
  "input",
  "select",
  "textarea",
  "summary",
  "[tabindex]",
  "[contenteditable='true']",
].join(",");

function skipped(el: HTMLElement): boolean {
  if (el.tabIndex < 0) return true;
  if ((el as HTMLButtonElement).disabled) return true;
  if (el instanceof HTMLInputElement && el.type === "hidden") return true;
  return el.closest("[hidden], [inert], [aria-hidden='true']") !== null;
}

/** What Tab visits inside `root`, in order. */
export function tabOrder(root: ParentNode = document.body): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => !skipped(el));
}

/** The name a test can match: aria-label, else aria-labelledby, else a <label>, else the text. */
export function nameOf(el: HTMLElement): string {
  const label = el.getAttribute("aria-label");
  if (label !== null) return label.trim();
  const by = el.getAttribute("aria-labelledby");
  if (by !== null) {
    return by
      .split(/\s+/)
      .map((id) => document.getElementById(id)?.textContent ?? "")
      .join(" ")
      .trim();
  }
  // Only labelable elements (inputs, buttons, textareas…) have `labels`.
  const labels = "labels" in el ? (el as HTMLInputElement).labels : null;
  if (labels !== null && labels.length > 0) {
    return [...labels]
      .map((l) => l.textContent)
      .join(" ")
      .trim();
  }
  return el.textContent.trim();
}

/** Where each named control sits in the tab order (-1 when Tab never reaches it). */
export function positions(root: ParentNode, names: readonly (string | RegExp)[]): number[] {
  const order = tabOrder(root).map(nameOf);
  return names.map((n) =>
    order.findIndex((name) => (typeof n === "string" ? name === n : n.test(name))),
  );
}
