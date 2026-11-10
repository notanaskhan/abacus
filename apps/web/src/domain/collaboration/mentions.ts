// Mention parsing for C-29 (P-05-T10). Text is plain text only (ADR-109): a mention is a known
// member's "@Name" in the body, rendered as a token by weight and background, never colour.

export interface Segment {
  text: string;
  mention: boolean;
}

/** The body split into plain text and "@Name" tokens for the people it mentions. */
export function segments(body: string, names: readonly string[]): Segment[] {
  const tokens = names.filter((n) => n.length > 0).map((n) => `@${n}`);
  if (tokens.length === 0) return body ? [{ text: body, mention: false }] : [];
  const out: Segment[] = [];
  let rest = body;
  while (rest.length > 0) {
    let at = -1;
    let hit = "";
    for (const token of tokens) {
      const i = rest.indexOf(token);
      if (i >= 0 && (at < 0 || i < at || (i === at && token.length > hit.length))) {
        at = i;
        hit = token;
      }
    }
    if (at < 0) {
      out.push({ text: rest, mention: false });
      break;
    }
    if (at > 0) out.push({ text: rest.slice(0, at), mention: false });
    out.push({ text: hit, mention: true });
    rest = rest.slice(at + hit.length);
  }
  return out;
}

/** The "@query" being typed at the caret, if any: where it starts and what follows "@". */
export function activeMention(
  text: string,
  caret: number,
): { start: number; query: string } | null {
  const before = text.slice(0, caret);
  const at = before.lastIndexOf("@");
  if (at < 0) return null;
  if (at > 0 && !/\s/.test(before[at - 1] ?? "")) return null;
  const query = before.slice(at + 1);
  if (/[\n@]/.test(query) || query.length > 40) return null;
  return { start: at, query };
}

/** The text with the "@query" at `start` replaced by "@Name ". */
export function insertMention(text: string, start: number, caret: number, name: string): string {
  return `${text.slice(0, start)}@${name} ${text.slice(caret)}`;
}
