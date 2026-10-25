import type { JSX } from "react";
import { sanitiseAgentText } from "../agent-text";
import { StatusPill } from "../components/status";
import { amount, count, DASH, pct } from "../format";
import { STATUS_REGISTRY } from "../status.gen";
import { CiteMarker } from "../tracing/cite";
import type { CitationView } from "../tracing/types";

// AgentBlocks v1 renderer (P-09-T06; P-09 §3.7; DEC-41): the server validated the payload
// (`agents/blocks.py`), and this renders React nodes only. Every string passes
// sanitiseAgentText, every fact goes through format.ts, every cite is a CiteMarker, and an
// unknown part renders a neutral row with no raw payload. AgentProse is the paragraph part alone.

export type BlockSegment =
  | { kind: "text"; text: string }
  | { kind: "cite"; citation_id: string; n: number }
  | { kind: "fact"; fact_id: string };

export type BlockPart =
  | { kind: "p"; segments: BlockSegment[] }
  | { kind: "table"; head: string[]; rows: BlockSegment[][] }
  | { kind: "kv"; rows: { label: string; value: BlockSegment[] }[] }
  | { kind: "metric"; label: string; fact_id: string }
  | { kind: "file"; artifact_id: string; name: string; meta?: string | null }
  | { kind: "badge"; object: string; code: string }
  | { kind: "cite_list"; cites: { kind: "cite"; citation_id: string; n: number }[] }
  | {
      kind: "options";
      options: { key: string; title: string; detail?: string | null; recommended?: boolean }[];
    }
  | { kind: "entity_ref"; record_type: string; record_id: string };

export interface AgentBlocksPayload {
  version?: number;
  /** Validated on the server; an unknown kind renders a neutral row. */
  parts: readonly (BlockPart | { kind: string })[];
}

/** A figure code computed and registered for the run (ADR-050). */
export interface BlockFact {
  kind: "money" | "count" | "percent" | "date" | "number";
  value: string;
}

export interface AgentBlocksProps {
  blocks: AgentBlocksPayload;
  facts: Readonly<Record<string, BlockFact>>;
  /** The run's citations by id; a cite with no view renders its bare number. */
  cites?: Readonly<Record<string, CitationView>>;
  /** Labels for entity refs, rendered by code (never by the model). */
  entityLabel?: (recordType: string, recordId: string) => string;
}

/** A fact through format.ts; an unknown fact id renders a dash, never the id. */
export function factText(fact: BlockFact | undefined): string {
  if (fact === undefined) return DASH;
  switch (fact.kind) {
    case "money":
      return amount(fact.value, "money", { zero: "explicit" }).text;
    case "count":
    case "number":
      return count(fact.value);
    case "percent":
      return pct(fact.value);
    case "date":
      return fact.value;
  }
}

function Segments({
  segments,
  facts,
  cites,
}: {
  segments: readonly BlockSegment[];
  facts: AgentBlocksProps["facts"];
  cites: AgentBlocksProps["cites"];
}): JSX.Element {
  const list = cites === undefined ? [] : Object.values(cites);
  return (
    <>
      {segments.map((seg, i) => {
        const key = `${seg.kind}-${String(i)}`;
        if (seg.kind === "text") return <span key={key}>{sanitiseAgentText(seg.text)}</span>;
        if (seg.kind === "fact") {
          return (
            <span key={key} data-fact={seg.fact_id} className="tabular-nums">
              {factText(facts[seg.fact_id])}
            </span>
          );
        }
        const view = cites?.[seg.citation_id];
        return view === undefined ? (
          <sup key={key} className="text-ink-3">
            {seg.n}
          </sup>
        ) : (
          <CiteMarker key={key} cite={view} list={list} />
        );
      })}
    </>
  );
}

function Part({
  part,
  facts,
  cites,
  entityLabel,
}: { part: { kind: string } } & Omit<AgentBlocksProps, "blocks">): JSX.Element {
  const p = part as BlockPart;
  switch (p.kind) {
    case "p":
      return (
        <p className="text-para">
          <Segments segments={p.segments} facts={facts} cites={cites} />
        </p>
      );
    case "table":
      return (
        <table className="w-full text-dense">
          <thead>
            <tr>
              {p.head.map((h, i) => (
                <th key={String(i)} className="text-left font-medium text-ink-3">
                  {sanitiseAgentText(h)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {p.rows.map((row, r) => (
              <tr key={String(r)}>
                {row.map((cell, c) => (
                  <td key={String(c)}>
                    <Segments segments={[cell]} facts={facts} cites={cites} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );
    case "kv":
      return (
        <dl className="grid grid-cols-[96px_1fr] gap-x-2 gap-y-1 text-dense">
          {p.rows.map((row, i) => (
            <div key={String(i)} className="contents">
              <dt className="text-ink-3">{sanitiseAgentText(row.label)}</dt>
              <dd>
                <Segments segments={row.value} facts={facts} cites={cites} />
              </dd>
            </div>
          ))}
        </dl>
      );
    case "metric":
      return (
        <div className="flex flex-col">
          <span className="text-dense text-ink-3">{sanitiseAgentText(p.label)}</span>
          <span className="text-title tabular-nums">{factText(facts[p.fact_id])}</span>
        </div>
      );
    case "file":
      return (
        <p className="text-dense">
          <span className="font-medium">{sanitiseAgentText(p.name)}</span>
          {p.meta != null && (
            <span className="text-ink-3">{` · ${sanitiseAgentText(p.meta)}`}</span>
          )}
        </p>
      );
    case "badge": {
      const codes = (STATUS_REGISTRY as Record<string, Record<string, { label: string }>>)[
        p.object
      ];
      const word = codes?.[p.code];
      return word === undefined ? <UnknownPart /> : <StatusPill>{word.label}</StatusPill>;
    }
    case "cite_list":
      return (
        <p className="text-dense">
          <Segments segments={p.cites} facts={facts} cites={cites} />
        </p>
      );
    case "options":
      return (
        <ul className="flex flex-col gap-1 text-dense">
          {p.options.map((o) => (
            <li key={o.key}>
              <span className="font-medium">{sanitiseAgentText(o.title)}</span>
              {o.recommended === true && <span className="text-ink-3"> · Recommended</span>}
              {o.detail != null && (
                <span className="block text-ink-2">{sanitiseAgentText(o.detail)}</span>
              )}
            </li>
          ))}
        </ul>
      );
    case "entity_ref":
      return (
        <p className="text-dense">
          {entityLabel === undefined
            ? p.record_type.replaceAll("_", " ")
            : entityLabel(p.record_type, p.record_id)}
        </p>
      );
    default:
      return <UnknownPart />;
  }
}

function UnknownPart(): JSX.Element {
  return <p className="text-dense text-ink-3">This part can&apos;t be shown.</p>;
}

/** AgentBlocks v1: agent-authored output as React nodes, never markup. */
export function AgentBlocks({ blocks, facts, cites, entityLabel }: AgentBlocksProps): JSX.Element {
  return (
    <div data-agent-blocks="v1" className="flex flex-col gap-2">
      {blocks.parts.map((part, i) => (
        <Part
          key={String(i)}
          part={part}
          facts={facts}
          {...(cites === undefined ? {} : { cites })}
          {...(entityLabel === undefined ? {} : { entityLabel })}
        />
      ))}
    </div>
  );
}

/** AgentProse: one paragraph of segments (narration), the same rules. */
export function AgentProse({
  segments,
  facts,
  cites,
}: {
  segments: readonly BlockSegment[];
  facts: AgentBlocksProps["facts"];
  cites?: AgentBlocksProps["cites"];
}): JSX.Element {
  return (
    <p className="text-para">
      <Segments segments={segments} facts={facts} cites={cites} />
    </p>
  );
}
