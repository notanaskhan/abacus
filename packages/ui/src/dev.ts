// Development assertions (plan 04 section 5.2 rule 9; quality strategy L3). They throw while the
// app runs in development, the gallery or a test, and cost nothing in a production build, where
// Vite replaces `import.meta.env.DEV` with false.

const DEV = (import.meta as { env?: { DEV?: boolean } }).env?.DEV === true;

/** Throw `message` when `condition` is false, in development only. */
export function devAssert(condition: boolean, message: string): void {
  if (DEV && !condition) throw new Error(message);
}

/** The text a node reads as: strings and numbers, through elements and fragments. */
export function textOf(node: unknown): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (typeof node === "object" && node !== null && "props" in node) {
    const props = (node as { props?: { children?: unknown } }).props;
    return textOf(props?.children);
  }
  return "";
}

/** The label of a control that opens a dialog ends in one U+2026, never three full stops. */
export function assertDialogLabel(label: string, what: string): void {
  const text = label.trim();
  devAssert(
    text === "" || text.endsWith("…"),
    `${what} opens a dialog, so its label must end with "…" (U+2026), not "${text}"`,
  );
}
