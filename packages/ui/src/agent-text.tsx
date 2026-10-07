// Model output is untrusted (ADR-052, ADR-065): it is rendered as plain text only, never as HTML
// or markdown, and never as a link. React text nodes can't carry markup; this also removes
// characters that can disguise text (controls, bidirectional overrides, zero-width marks) and
// caps the length, so a hostile rationale can't reorder or hide what a reviewer reads.
import type { JSX } from "react";

export const AGENT_TEXT_LIMIT = 2000;
const MAX_BLANK_LINES = 1;

// Characters that hide, disguise or reorder text: C0/C1 controls except tab and newline; the
// soft hyphen and invisible joiners/fillers; Arabic letter mark; zero-width and bidirectional
// marks, embeddings, overrides and isolates; line/paragraph separators; variation selectors;
// interlinear annotation and object replacement; the BOM; Unicode tag characters (invisible
// "ASCII smuggling") and supplementary variation selectors.
const HIDDEN = new RegExp(
  [
    "[\\u0000-\\u0008\\u000B-\\u001F\\u007F-\\u009F]",
    "[\\u00AD\\u034F\\u061C\\u115F\\u1160\\u17B4\\u17B5\\u180B-\\u180F]",
    "[\\u200B-\\u200F\\u2028-\\u202E\\u2060-\\u206F\\u2800\\u3164]",
    "[\\uFE00-\\uFE0F\\uFEFF\\uFFA0\\uFFF9-\\uFFFC]",
    "[\\u{E0000}-\\u{E007F}\\u{E0100}-\\u{E01EF}]",
  ].join("|"),
  "gu",
);

export function sanitiseAgentText(text: string, limit: number = AGENT_TEXT_LIMIT): string {
  const visible = text
    .normalize("NFC")
    .replace(/\r\n?/g, "\n") // before stripping controls: a lone CR is a line break, not noise
    .replace(HIDDEN, "")
    .replace(
      new RegExp(`\\n{${String(MAX_BLANK_LINES + 2)},}`, "g"),
      "\n".repeat(MAX_BLANK_LINES + 1),
    );
  const chars = Array.from(visible);
  return chars.length > limit ? `${chars.slice(0, limit).join("")}…` : visible;
}

export interface AgentTextProps {
  /** Text a model produced (rationale, quotes, unverified notes). */
  text: string;
  /** Inline (a quote within a sentence) or a block that keeps the model's line breaks. */
  inline?: boolean;
  className?: string;
}

export function AgentText({ text, inline = false, className }: AgentTextProps): JSX.Element {
  const Tag = inline ? "span" : "p";
  return (
    <Tag
      className={[inline ? "" : "whitespace-pre-line", "[overflow-wrap:anywhere]", className ?? ""]
        .join(" ")
        .trim()}
    >
      {sanitiseAgentText(text)}
    </Tag>
  );
}
