// T14 GraphCanvasLayout (F-07-T16; F-07 §G1–G4; handoff T14 and TPL-14 a–f). The record's frame for
// a relationship graph: the subbar and tabsbar slots, the canvas pane (header: Graph · List,
// "Relationships", "+ Add relationship"; the 36 h dependency banner, amber while K-1s are at risk
// and green once released, with "Open 1065 ›"; the canvas or the list body) and the 330 inspector
// (OverviewCard, KV rows with the masked TIN and its "Reveal (logged)" intent, the K-1 band and the
// linked work). It fetches nothing and decides nothing: Reveal, Add relationship, Open and the view
// toggle are intents; the host logs a reveal before it answers the value.
//
// TIN (ADR-031, DEC-52): the slot draws only a last-four mask ("•••-••-4417", "••-•••0287"); any
// other value draws "—". A revealed value shows for `REMASK_MS` (10 s), then re-masks; Reveal is
// absent unless the viewer holds the capability (`canReveal`). Firm-only (INV-4, F-07-T20).
import { type JSX, type ReactNode, useEffect, useState } from "react";
import { cn } from "../cn";
import { Button } from "../components/button";
import { Pill } from "../components/pill";
import { Segmented } from "../components/tabs";
import { EmptyState } from "../components/states";
import { Icon } from "../icons";
import { OverviewCard } from "../record/record-kit";

export const REMASK_MS = 10_000;
export const GRAPH_GEOMETRY = { header: 46, banner: 36, inspector: 330, gap: 10 } as const;

/** A last-four TIN mask: SSN `•••-••-dddd` or EIN `••-•••dddd`. */
const MASK = /^(?:•••-••-\d{4}|••-•••\d{4})$/u;

export function isTinMask(value: string): boolean {
  return MASK.test(value);
}

export type GraphView = "graph" | "list";

export interface DependencyBanner {
  tone: "at_risk" | "released";
  text: string;
  action?: { label: string; onClick: () => void } | undefined;
}

export interface InspectorKv {
  key: string;
  label: string;
  /** Lines of the value (a role per line). */
  lines: readonly string[];
}

export interface K1BandRow {
  key: string;
  label: string;
  /** A decimal string; the kit formats it, never sums it. */
  amount: string;
}

export interface LinkedWork {
  id: string;
  title: string;
  onOpen?: (() => void) | undefined;
}

export interface GraphInspector {
  title: string;
  sub: string;
  icon?: "user" | "building-2" | "landmark" | "file-text";
  /** The server's mask; anything that is not a last-four mask draws "—". */
  tin?: string | null;
  kv: readonly InspectorKv[];
  k1?: {
    title: string;
    rows: readonly K1BandRow[];
    status: { text: string; tone: "amber" | "green"; sub?: string };
  } | null;
  linked?: readonly LinkedWork[];
}

export interface RelationshipRow {
  id: string;
  from: string;
  relationship: string;
  to: string;
  since: string;
  source: string;
}

export interface GraphCanvasLayoutProps {
  subbar?: ReactNode;
  tabsbar?: ReactNode;
  view: GraphView;
  onView?: (view: GraphView) => void;
  banner?: DependencyBanner | null;
  /** The canvas (GraphCanvas) for the graph view. */
  canvas: ReactNode;
  /** The list view's rows (T1 grammar: From · Relationship · To · Since · Source). */
  rows?: readonly RelationshipRow[];
  inspector?: GraphInspector | null;
  /** One entity and no relationships: the EmptyState instead of the canvas. */
  single?: boolean;
  /** The viewer holds the reveal capability; absent, Reveal is not drawn. */
  canReveal?: boolean;
  /** The host logs the reveal and answers the full value (or null when refused). */
  onReveal?: () => Promise<string | null>;
  onAddRelationship?: () => void;
  className?: string;
}

export function MaskedTin({
  value,
  canReveal,
  onReveal,
}: {
  value: string | null | undefined;
  canReveal: boolean;
  onReveal?: (() => Promise<string | null>) | undefined;
}): JSX.Element {
  const [shown, setShown] = useState<string | null>(null);
  useEffect(() => {
    if (shown === null) return undefined;
    const timer = setTimeout(() => setShown(null), REMASK_MS);
    return () => clearTimeout(timer);
  }, [shown]);
  const masked = value !== null && value !== undefined && isTinMask(value) ? value : "—";
  return (
    <span className="flex items-center gap-[6px]">
      <span data-tin={shown === null ? "masked" : "revealed"} className="tabular-nums">
        {shown ?? masked}
      </span>
      {canReveal && onReveal !== undefined && shown === null && masked !== "—" ? (
        <button
          type="button"
          onClick={() => {
            void onReveal().then((v) => {
              if (v !== null) setShown(v);
            });
          }}
          className="rounded-pill bg-nested px-[6px] text-[11px] text-ink-2"
        >
          Reveal (logged)
        </button>
      ) : null}
    </span>
  );
}

function Banner({ banner }: { banner: DependencyBanner }): JSX.Element {
  const risk = banner.tone === "at_risk";
  return (
    <div
      role="status"
      data-banner={banner.tone}
      style={{ height: GRAPH_GEOMETRY.banner }}
      className={cn(
        "mb-[10px] flex items-center gap-[8px] rounded-[10px] px-[12px] text-[12.5px] font-medium",
        risk ? "bg-amber-tint text-amber-ink" : "bg-green-tint text-green-ink",
      )}
    >
      <Icon name={risk ? "triangle-alert" : "circle-check"} size={14} />
      <span className="min-w-0 flex-1 truncate">{banner.text}</span>
      {banner.action ? (
        <Button variant="ghost" size="sm" onClick={banner.action.onClick}>
          {banner.action.label}
        </Button>
      ) : null}
    </div>
  );
}

function Inspector({
  data,
  canReveal,
  onReveal,
}: {
  data: GraphInspector;
  canReveal: boolean;
  onReveal?: (() => Promise<string | null>) | undefined;
}): JSX.Element {
  return (
    <aside
      aria-label={data.title}
      style={{ width: GRAPH_GEOMETRY.inspector }}
      className="flex min-h-0 flex-none flex-col overflow-y-auto rounded-pane bg-card"
    >
      <header style={{ height: GRAPH_GEOMETRY.header }} className="flex flex-none items-center justify-center text-[14.5px] font-medium">
        {data.title}
      </header>
      <OverviewCard icon={data.icon ?? "user"} title={data.title} sub={data.sub} />
      <dl className="flex flex-col">
        {data.tin !== undefined ? (
          <div className="flex min-h-[33px] items-center gap-[8px] px-[12px] text-body hairline-b">
            <dt className="w-[96px] flex-none text-ink-2">TIN</dt>
            <dd className="min-w-0 flex-1">
              <MaskedTin value={data.tin} canReveal={canReveal} onReveal={onReveal} />
            </dd>
          </div>
        ) : null}
        {data.kv.map((row) => (
          <div key={row.key} className="flex min-h-[33px] items-start gap-[8px] px-[12px] py-[6px] text-body hairline-b">
            <dt className="w-[96px] flex-none text-ink-2">{row.label}</dt>
            <dd className="flex min-w-0 flex-1 flex-col">
              {row.lines.map((line) => (
                <span key={line}>{line}</span>
              ))}
            </dd>
          </div>
        ))}
      </dl>
      {data.k1 ? (
        <section aria-label={data.k1.title} className="mt-[10px]">
          <p className="px-[12px] text-[11px] font-medium uppercase tracking-[0.04em] text-ink-3">{data.k1.title}</p>
          <ul>
            {data.k1.rows.map((r) => (
              <li key={r.key} className="flex min-h-[30px] items-center px-[12px] text-body hairline-b">
                <span className="flex-1 text-ink-2">{r.label}</span>
                <span className="tabular-nums">{formatWhole(r.amount)}</span>
              </li>
            ))}
            <li className="flex min-h-[30px] items-center gap-[6px] px-[12px] text-body">
              <span className="flex-1 text-ink-2">Status</span>
              <Pill variant={data.k1.status.tone}>{data.k1.status.text}</Pill>
            </li>
            {data.k1.status.sub ? (
              <li className="px-[12px] text-[11.5px] text-ink-3">{data.k1.status.sub}</li>
            ) : null}
          </ul>
        </section>
      ) : null}
      {data.linked && data.linked.length > 0 ? (
        <section aria-label="Linked work" className="mt-[10px] pb-[10px]">
          <p className="px-[12px] text-[11px] font-medium uppercase tracking-[0.04em] text-ink-3">Linked work</p>
          {data.linked.map((w) => (
            <button
              key={w.id}
              type="button"
              onClick={w.onOpen}
              className="flex min-h-[33px] w-full items-center px-[12px] text-left text-body hover:bg-nested"
            >
              <span className="flex-1 truncate">{w.title}</span>
              <Icon name="chevron-right" size={12} className="text-ink-3" />
            </button>
          ))}
        </section>
      ) : null}
    </aside>
  );
}

function formatWhole(amount: string): string {
  const n = Number(amount);
  if (!Number.isFinite(n)) return amount;
  const s = Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 0 });
  return n < 0 ? `(${s})` : s;
}

function ListBody({ rows }: { rows: readonly RelationshipRow[] }): JSX.Element {
  return (
    <table className="w-full border-collapse text-body" aria-label="Relationships">
      <thead>
        <tr className="h-[32px] text-left text-ink-3">
          {["From", "Relationship", "To", "Since", "Source"].map((h) => (
            <th key={h} scope="col" className="px-[10px] font-medium">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} className="h-[33px] hairline-b">
            <td className="px-[10px]">{r.from}</td>
            <td className="px-[10px]">{r.relationship}</td>
            <td className="px-[10px]">{r.to}</td>
            <td className="px-[10px] tabular-nums">{r.since}</td>
            <td className="px-[10px] text-ink-2">{r.source}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function GraphCanvasLayout({
  subbar,
  tabsbar,
  view,
  onView,
  banner,
  canvas,
  rows = [],
  inspector,
  single = false,
  canReveal = false,
  onReveal,
  onAddRelationship,
  className,
}: GraphCanvasLayoutProps): JSX.Element {
  return (
    <div data-template="T14" className={cn("flex min-h-0 flex-1 flex-col", className)}>
      {subbar ? <div className="flex-none">{subbar}</div> : null}
      {tabsbar ? <div className="flex-none">{tabsbar}</div> : null}
      <div className="flex min-h-0 flex-1 gap-[10px] p-[12px]">
        <section aria-label="Relationships" className="flex min-h-0 min-w-0 flex-1 flex-col rounded-pane bg-card">
          <header style={{ height: GRAPH_GEOMETRY.header }} className="flex flex-none items-center gap-[8px] px-[12px]">
            <Segmented
              size="small"
              label="Relationships view"
              options={["Graph", "List"]}
              active={view === "list" ? "List" : "Graph"}
              {...(onView === undefined ? {} : { onChange: (l: string) => onView(l === "List" ? "list" : "graph") })}
            />
            <span className="flex-1 text-center text-[14.5px] font-medium">Relationships</span>
            <Button variant="secondary" size="sm" onClick={onAddRelationship}>
              + Add relationship
            </Button>
          </header>
          <div className="min-h-0 flex-1 overflow-auto bg-shell p-[12px]">
            {banner ? <Banner banner={banner} /> : null}
            {single ? (
              <>
                {canvas}
                <EmptyState
                  title="No relationships yet."
                  action={
                    <Button variant="secondary" size="sm" onClick={onAddRelationship}>
                      + Add relationship
                    </Button>
                  }
                />
              </>
            ) : view === "list" ? (
              <ListBody rows={rows} />
            ) : (
              canvas
            )}
          </div>
        </section>
        {inspector ? <Inspector data={inspector} canReveal={canReveal} onReveal={onReveal} /> : null}
      </div>
    </div>
  );
}
