// Model output is untrusted (ADR-052, ADR-065): it is rendered as plain text only, never as HTML
// or markdown, and never as a link. React text nodes can't carry markup; this also removes
// characters that can disguise text (controls, bidirectional overrides, zero-width marks) and
// caps the length, so a hostile rationale can't reorder or hide what a reviewer reads.
import type { JSX } from "react";

export const AGENT_TEXT_LIMIT = 2000;

// C0/C1 controls except tab and newline; bidi embeddings, overrides and isolates; zero-width and
// invisible formatting characters; the byte-order mark.
const HIDDEN = /[\u0000-\u0008\u000B-\u001F\u007F-\u009F​-‏‪-‮⁠-⁩﻿]/g;

export function sanitiseAgentText(text: string, limit: number = AGENT_TEXT_LIMIT): string {
  const visible = text.replace(HIDDEN, "").replace(/\r\n?/g, "\n");
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
    <Tag className={className} style={inline ? undefined : { whiteSpace: "pre-line" }}>
      {sanitiseAgentText(text)}
    </Tag>
  );
}
