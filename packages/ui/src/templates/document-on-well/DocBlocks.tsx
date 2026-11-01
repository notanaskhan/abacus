import type { JSX, ReactNode } from "react";
import { AgentText } from "../../agent-text";
import { cn } from "../../cn";
import { CiteMarker } from "../../tracing/cite";
import type { CitationView } from "../../tracing/types";
import type { DocumentVariant } from "./types";

// T10 DocBlocks (F-06-T15; ADR-230 / P-24; F-06.md §3 F4, §5.2; SPEC-400 AC-19, AC-21): the paper's
// body as a closed union of blocks over P-24 segments, rendered as React nodes only — never an
// HTML string, never markdown, never "[n]" parsed from text (a "[3]" in text is literal text).
//
// - A segment is `text`, `fact` (digits code already formatted, ADR-050) or `cite` (a marker
//   number and the citation it points to). A `cite` renders a CiteMarker only with a typed,
//   verified locator (INV-2); otherwise nothing.
// - A block's provenance is `agent`, `human` or `template`. Agent text renders through AgentText.
//   A `letter` or `email` drops agent blocks unless the consumer passes `modelTextToClients`
//   (ADR P-25 off, R12): client-facing paper is template text only.
// - A human edit of a block is marked under it ("Edited by Hannah Leclerc"), never hidden.

export type DocSegment =
  | { kind: "text"; text: string }
  | { kind: "fact"; text: string }
  | { kind: "cite"; n: number; citation?: CitationView; verified?: boolean };

export type Provenance = "agent" | "human" | "template";

interface Provenanced {
  provenance: Provenance;
  /** A person's edit of an agent block: the mark under it. */
  editedBy?: string;
}

export type DocBlock =
  | ({ kind: "h"; level: 3 | 4; text: string } & Provenanced)
  | ({ kind: "p"; segments: readonly DocSegment[] } & Provenanced)
  | ({ kind: "ul"; items: readonly (readonly DocSegment[])[] } & Provenanced)
  | ({
      kind: "table";
      caption?: string;
      head: readonly string[];
      rows: readonly { cells: readonly (readonly DocSegment[])[]; total?: boolean }[];
    } & Provenanced)
  | { kind: "letterhead"; firm: string; lines: readonly string[] }
  | { kind: "signature"; name: string; title: string; firm?: string; signed?: string };

export interface DocBlocksProps {
  blocks: readonly DocBlock[];
  variant: DocumentVariant;
  /** ADR P-25; omitted = off. */
  modelTextToClients?: boolean;
  /** "Edited by {name}" (the consumer's copy). */
  editedLabel?: (name: string) => string;
}

/** Whether agent text may show on this variant (paper always; client-facing only under P-25). */
export function agentAllowed(variant: DocumentVariant, modelTextToClients?: boolean): boolean {
  return variant === "paper" || modelTextToClients === true;
}

/** A cite renders a marker only for a typed, verified locator (INV-2). */
function citeShown(segment: Extract<DocSegment, { kind: "cite" }>): boolean {
  return (
    segment.verified === true &&
    segment.citation !== undefined &&
    segment.citation.loc.trim() !== "" &&
    segment.citation.n === segment.n
  );
}

function Segments({
  segments,
  agent,
}: {
  segments: readonly DocSegment[];
  agent: boolean;
}): JSX.Element {
  const cites = segments.flatMap((s) =>
    s.kind === "cite" && citeShown(s) && s.citation !== undefined ? [s.citation] : [],
  );
  return (
    <>
      {segments.map((s, i) => {
        const key = `${s.kind}-${String(i)}`;
        if (s.kind === "cite") {
          return citeShown(s) && s.citation !== undefined ? (
            <CiteMarker key={key} cite={s.citation} list={cites} />
          ) : null;
        }
        if (s.kind === "fact") {
          return (
            <span key={key} data-doc="fact" className="tabular-nums">
              {s.text}
            </span>
          );
        }
        return agent ? (
          <AgentText key={key} text={s.text} inline />
        ) : (
          <span key={key}>{s.text}</span>
        );
      })}
    </>
  );
}

function Edited({
  name,
  label,
}: {
  name: string;
  label: ((name: string) => string) | undefined;
}): JSX.Element {
  return (
    <span data-doc="edited" className="mt-[2px] block text-meta text-ink-3">
      {label === undefined ? `Edited by ${name}` : label(name)}
    </span>
  );
}

function Block({
  block,
  editedLabel,
}: {
  block: DocBlock;
  editedLabel?: (name: string) => string;
}): ReactNode {
  switch (block.kind) {
    case "letterhead":
      return (
        <header data-doc="letterhead" className="mb-[18px] border-b border-hair pb-[12px]">
          <p className="text-[15px] font-medium">{block.firm}</p>
          {block.lines.map((line) => (
            <p key={line} className="text-meta text-ink-3">
              {line}
            </p>
          ))}
        </header>
      );
    case "signature":
      return (
        <footer data-doc="signature" className="mt-[24px] flex flex-col gap-[2px]">
          {block.signed !== undefined && <p className="text-meta text-ink-3">{block.signed}</p>}
          <p className="text-body font-medium">{block.name}</p>
          <p className="text-meta text-ink-2">{block.title}</p>
          {block.firm !== undefined && <p className="text-meta text-ink-2">{block.firm}</p>}
        </footer>
      );
    case "h": {
      const Tag = block.level === 3 ? "h3" : "h4";
      return (
        <Tag
          data-doc="section-heading"
          className={cn(
            "mt-[14px] mb-[6px] font-medium",
            block.level === 3 ? "text-[14px]" : "text-dense",
          )}
        >
          {block.provenance === "agent" ? <AgentText text={block.text} inline /> : block.text}
        </Tag>
      );
    }
    case "p":
      return (
        <div data-doc="paragraph" className="mb-[10px]">
          <p className="text-paragraph text-ink">
            <Segments segments={block.segments} agent={block.provenance === "agent"} />
          </p>
          {block.editedBy !== undefined && <Edited name={block.editedBy} label={editedLabel} />}
        </div>
      );
    case "ul":
      return (
        <div data-doc="bullets" className="mb-[10px]">
          <ul className="list-disc pl-[18px] text-paragraph">
            {block.items.map((item, i) => (
              <li key={`li-${String(i)}`}>
                <Segments segments={item} agent={block.provenance === "agent"} />
              </li>
            ))}
          </ul>
          {block.editedBy !== undefined && <Edited name={block.editedBy} label={editedLabel} />}
        </div>
      );
    case "table":
      return (
        <div data-doc="table" className="mb-[12px]">
          <table className="w-full border-collapse text-cell">
            {block.caption !== undefined && (
              <caption className="pb-[4px] text-left text-meta text-ink-3">
                {block.caption}
              </caption>
            )}
            <thead>
              <tr>
                {block.head.map((h, i) => (
                  <th
                    key={`th-${String(i)}`}
                    scope="col"
                    className={cn(
                      "border-b border-hair py-[4px] text-th font-medium text-ink-2",
                      i === 0 ? "text-left" : "text-right",
                    )}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, r) => (
                <tr
                  key={`tr-${String(r)}`}
                  data-total={row.total === true ? "" : undefined}
                  className={cn(row.total === true && "border-t border-ink-4 font-medium")}
                >
                  {row.cells.map((cell, c) => (
                    <td
                      key={`td-${String(c)}`}
                      className={cn("py-[3px]", c === 0 ? "text-left" : "text-right tabular-nums")}
                    >
                      <Segments segments={cell} agent={block.provenance === "agent"} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {block.editedBy !== undefined && <Edited name={block.editedBy} label={editedLabel} />}
        </div>
      );
  }
}

/** The paper's body: each block as React nodes, agent blocks only where they may show. */
export function DocBlocks({
  blocks,
  variant,
  modelTextToClients,
  editedLabel,
}: DocBlocksProps): JSX.Element {
  const agent = agentAllowed(variant, modelTextToClients);
  const shown = blocks.filter(
    (b) => b.kind === "letterhead" || b.kind === "signature" || agent || b.provenance !== "agent",
  );
  return (
    <div data-doc="blocks" data-variant={variant}>
      {shown.map((b, i) => (
        <Block
          key={`${b.kind}-${String(i)}`}
          block={b}
          {...(editedLabel === undefined ? {} : { editedLabel })}
        />
      ))}
    </div>
  );
}

/** T10e: the email variant at its two widths, 600 (desktop) and 390 (phone), on the well. */
export function EmailFrame({
  width,
  children,
}: {
  width: 600 | 390;
  children: ReactNode;
}): JSX.Element {
  return (
    <article
      data-document="email"
      data-width={width}
      className={cn(
        "mx-auto flex-none overflow-hidden rounded-pane bg-card px-[24px] pt-[20px] pb-[24px] text-body text-ink shadow-e2",
        width === 600 ? "w-[600px]" : "w-[390px] px-[16px]",
      )}
    >
      {children}
    </article>
  );
}
