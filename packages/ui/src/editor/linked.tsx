// F-08-T29 (DEC-6027; C-37): linked values on paper. A `linkedValue` is an inline atom: its
// figure is the consumer's (TB-linked groups, a formula, or a person's override; ADR-050), drawn
// with the shared dotted underline. It cannot be typed over, deleted or pasted into (protect.ts
// guards its attrs like a statement table's). Hover lights only that value (E1, one match per
// scope) and shows its lineage; a click opens the Lineage dock. A stale override sits on amber
// tint with "↺ Relink"; changing a number is only ever an intent: Relink, Override (a reason),
// or Insert linked value.
import { NodeViewWrapper, type ReactNodeViewProps } from "@tiptap/react";
import { type JSX, type ReactNode, createContext, useContext, useState } from "react";
import { cn } from "../cn";
import { useMatch } from "../tracing/match";
import type { MatchId } from "../tracing/types";
import { paperAmount } from "./format";

export type LinkedSource = "tb_linked" | "formula" | "override";

export interface LinkedValueAttrs {
  id: string;
  value: number;
  source: LinkedSource;
  /** An override whose linked groups now total something else (ADR-041 change detection). */
  stale: boolean;
  dollar: boolean;
}

export interface LineageGroup {
  label: string;
  account: string;
  amount: number;
}

export interface Lineage {
  title: string;
  subtitle: string;
  groups?: readonly LineageGroup[];
  formula?: string;
  override?: { value: number; by: string; reason: string; linkedNow: number | null };
  usedIn?: readonly { label: string; amount: number | null }[];
  priorYear?: string;
}

export interface LinkedValueHandlers {
  lineage: (id: string) => Lineage | undefined;
  onOpenLineage?: (id: string) => void;
  onRelink?: (id: string) => void;
}

const Handlers = createContext<LinkedValueHandlers>({ lineage: () => undefined });

export function LinkedValueProvider({
  value,
  children,
}: {
  value: LinkedValueHandlers;
  children: ReactNode;
}): JSX.Element {
  return <Handlers.Provider value={value}>{children}</Handlers.Provider>;
}

/** The shared dotted underline (C-37), reused by T22's linked cells. */
export const LINKED_UNDERLINE =
  "underline decoration-dotted decoration-ink-4 decoration-1 underline-offset-2";

export function LineagePopover({ lineage }: { lineage: Lineage }): JSX.Element {
  const total = lineage.groups?.reduce((n, g) => n + g.amount, 0);
  return (
    <span
      role="tooltip"
      data-lineage
      className="absolute left-0 top-full z-10 mt-[4px] block w-[300px] rounded-nested bg-card p-[12px] text-left font-sans text-[12.5px] text-ink shadow-e2"
    >
      <span className="block font-medium text-[13.5px]">{lineage.title}</span>
      <span className="block text-[11.5px] text-ink-3">{lineage.subtitle}</span>
      {lineage.groups?.map((g) => (
        <span key={g.account} className="flex h-[30px] items-center justify-between">
          <span>{`${g.label} · ${g.account}`}</span>
          <span className={cn("tabular-nums", g.amount < 0 && "text-negative")}>
            {paperAmount(g.amount)}
          </span>
        </span>
      ))}
      {total !== undefined ? (
        <span className="flex h-[30px] items-center justify-between border-t border-stroke font-medium">
          <span>Total</span>
          <span className="tabular-nums">{paperAmount(total)}</span>
        </span>
      ) : null}
      {lineage.formula !== undefined ? (
        <span className="block text-[11.5px] text-ink-3">{lineage.formula}</span>
      ) : null}
      {lineage.override !== undefined ? (
        <span className="block text-[11.5px] text-ink-3">
          {`Override ${paperAmount(lineage.override.value)} by ${lineage.override.by}: ${lineage.override.reason}`}
        </span>
      ) : null}
      {lineage.priorYear !== undefined ? (
        <span className="block text-[11.5px] text-ink-3">{lineage.priorYear}</span>
      ) : null}
    </span>
  );
}

export function LinkedValueView({ node }: ReactNodeViewProps): JSX.Element {
  const attrs = node.attrs as LinkedValueAttrs;
  const handlers = useContext(Handlers);
  // A line item's own id names its match (the server's line-item id), never model text (INV-2).
  const { lit, bind } = useMatch(`linked:${attrs.id}` as MatchId, "cell");
  const lineage = lit ? handlers.lineage(attrs.id) : undefined;
  const staleOverride = attrs.source === "override" && attrs.stale;
  return (
    <NodeViewWrapper
      as="span"
      contentEditable={false}
      data-linked={attrs.id}
      data-source={attrs.source}
      data-stale={staleOverride ? "true" : undefined}
      className="relative inline-block"
    >
      <span
        {...bind}
        role="button"
        tabIndex={0}
        aria-label={`${paperAmount(attrs.value)}, ${attrs.source.replace("_", "-")}${staleOverride ? ", stale override" : ""}`}
        onClick={() => handlers.onOpenLineage?.(attrs.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter") handlers.onOpenLineage?.(attrs.id);
        }}
        className={cn(
          "rounded-[4px] tabular-nums",
          LINKED_UNDERLINE,
          staleOverride && "bg-amber-tint",
          lit && "bg-match-bg inset-shadow-match",
        )}
      >
        {paperAmount(attrs.value, attrs.dollar)}
      </span>
      {staleOverride ? (
        <button
          type="button"
          data-relink={attrs.id}
          onClick={() => handlers.onRelink?.(attrs.id)}
          className="ml-[6px] font-sans text-[11px] font-medium text-amber-ink"
        >
          ↺ Relink
        </button>
      ) : null}
      {lineage !== undefined ? <LineagePopover lineage={lineage} /> : null}
    </NodeViewWrapper>
  );
}

/** "Override…" (C-37): a person's figure with a reason; the intent fires only with both. */
export function OverrideForm({
  current,
  onOverride,
  onCancel,
}: {
  current: number;
  onOverride: (value: number, reason: string) => void;
  onCancel: () => void;
}): JSX.Element {
  const [value, setValue] = useState(String(current));
  const [reason, setReason] = useState("");
  const parsed = Number(value.replace(/,/g, ""));
  const ready = reason.trim() !== "" && Number.isFinite(parsed) && value.trim() !== "";
  return (
    <form
      data-override-form
      className="flex flex-col gap-[8px] text-[12.5px]"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) onOverride(parsed, reason.trim());
      }}
    >
      <label className="flex flex-col gap-[4px]">
        <span>Amount</span>
        <input
          value={value}
          inputMode="numeric"
          onChange={(e) => {
            setValue(e.target.value);
          }}
          className="h-[30px] rounded-nested bg-nested px-[8px] tabular-nums"
        />
      </label>
      <label className="flex flex-col gap-[4px]">
        <span>Reason</span>
        <input
          value={reason}
          onChange={(e) => {
            setReason(e.target.value);
          }}
          className="h-[30px] rounded-nested bg-nested px-[8px]"
        />
      </label>
      <span className="flex gap-[8px]">
        <button
          type="submit"
          disabled={!ready}
          className="h-[28px] rounded-control bg-ink px-[10px] text-card disabled:opacity-40"
        >
          Override
        </button>
        <button type="button" onClick={onCancel} className="h-[28px] px-[10px]">
          Cancel
        </button>
      </span>
    </form>
  );
}
