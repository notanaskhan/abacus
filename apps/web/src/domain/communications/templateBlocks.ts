// A template block's text as the editor handles it (R-01-T25): plain words and `{variable}`
// tokens. The server renders and lints; this only splits text for chips and inserts a variable
// at the caret. Firm content: nothing here holds template words.

import { token } from "./variables";

export type Segment = { kind: "text"; text: string } | { kind: "variable"; name: string };

const PLACEHOLDER = /\{([a-z][a-z0-9_]{0,39})\}/g;

/** "Hi {client_first_name}," → text, variable, text. */
export function segments(text: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  for (const match of text.matchAll(PLACEHOLDER)) {
    const at = match.index;
    if (at > last) out.push({ kind: "text", text: text.slice(last, at) });
    out.push({ kind: "variable", name: match[1] ?? "" });
    last = at + match[0].length;
  }
  if (last < text.length) out.push({ kind: "text", text: text.slice(last) });
  return out;
}

/** Insert `{name}` into `text` at the caret (or over the selection); the caret after it. */
export function insertAt(
  text: string,
  name: string,
  start: number,
  end: number = start,
): { text: string; caret: number } {
  const from = Math.max(0, Math.min(start, text.length));
  const to = Math.max(from, Math.min(end, text.length));
  const inserted = token(name);
  return { text: text.slice(0, from) + inserted + text.slice(to), caret: from + inserted.length };
}
