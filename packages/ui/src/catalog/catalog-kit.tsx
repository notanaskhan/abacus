import { type JSX, type KeyboardEvent, type ReactNode, useRef } from "react";
import { cn } from "../cn";
import { Pill } from "../components/pill";
import { Skeleton } from "../components/states";
import { status } from "../status";

// The catalog grammar the C-11 AgentCard and the C-14 ConnectionTile share (F-05-T59; C-11 Agent
// Card Library and C-14 Connect kit handoffs, T5 and TPL-05): the card's status badge, the white
// card box (radius 12, e2, e3 on hover over 200ms, no translate), the CategoryList with its count
// pills, the three-column grid and the skeleton card. Words come from the status registry; the
// installed and connected states, which the registry gives as the olive check disc, draw as the
// kits' solid olive badge with its 10px check.

/** The registry states a catalog card can carry: `agent_template` and `integration` codes. */
export type CatalogBadgeState =
  | { object: "agent_template"; code: "available" | "installed" | "coming_soon" }
  | { object: "integration"; code: "available" | "connected" | "connecting" | "coming_soon" };

/** The badge at the card's top right: 22 high, 11.5/500. */
export function CatalogBadge({ state }: { state: CatalogBadgeState }): JSX.Element {
  const resolved =
    state.object === "agent_template"
      ? status("agent_template", state.code)
      : status("integration", state.code);
  const done = state.code === "installed" || state.code === "connected";
  if (done) {
    return (
      <Pill variant="green" size="outline" check data-badge={state.code}>
        {resolved.label}
      </Pill>
    );
  }
  if (state.code === "connecting") {
    return (
      <Pill variant="outline" size="outline" spin role="status" data-badge={state.code}>
        {`${resolved.label}…`}
      </Pill>
    );
  }
  return (
    <Pill variant={resolved.variant ?? "outline"} size="outline" data-badge={state.code}>
      {resolved.label}
    </Pill>
  );
}

export interface CatalogCardProps {
  /** "{name}, {status}": the listitem's accessible name. */
  label: string;
  /** 210 for an agent, 212 for an integration. */
  height: 210 | 212;
  /** A coming-soon card does not lift on hover. */
  still?: boolean;
  children: ReactNode;
  className?: string;
}

/** The card box: a white column, padding 14, the action on its bottom edge. */
export function CatalogCard({
  label,
  height,
  still = false,
  children,
  className,
}: CatalogCardProps): JSX.Element {
  return (
    <li
      aria-label={label}
      data-catalog-card=""
      className={cn(
        "flex min-w-0 flex-col rounded-pane bg-card p-[14px] shadow-e2",
        height === 210 ? "h-[210px]" : "h-[212px]",
        !still &&
          "transition-shadow duration-[200ms] hover:shadow-e3 motion-reduce:transition-none",
        "has-[:focus-visible]:shadow-e2",
        className,
      )}
    >
      {children}
    </li>
  );
}

/** The skeleton card: the same box with a 34 tile and three bars at 58, 92 and 74%. */
export function CatalogSkeletonCard({ height = 210 }: { height?: 210 | 212 }): JSX.Element {
  return (
    <li
      aria-hidden="true"
      data-catalog-skeleton=""
      className={cn(
        "flex flex-col rounded-pane bg-card p-[14px] shadow-e2",
        height === 210 ? "h-[210px]" : "h-[212px]",
      )}
    >
      <Skeleton immediate className="size-[34px] rounded-tile" />
      <Skeleton immediate className="mt-[14px] h-[9px] w-[58%]" />
      <Skeleton immediate className="mt-[13px] h-[9px] w-[92%]" />
      <Skeleton immediate className="mt-[8px] h-[9px] w-[74%]" />
    </li>
  );
}

/** The three-column grid of cards, gap 12: a list, each card a listitem. */
export function CatalogGrid({
  label,
  busy = false,
  children,
}: {
  label: string;
  /** Skeleton cards hold the grid. */
  busy?: boolean;
  children: ReactNode;
}): JSX.Element {
  return (
    <ul
      aria-label={label}
      aria-busy={busy}
      data-catalog-grid=""
      className="grid grid-cols-3 gap-[12px]"
    >
      {children}
    </ul>
  );
}

export interface CatalogCategory {
  key: string;
  label: string;
  count: number;
  /** The 11.5 ink-3 line under the label: the row grows from 33 to 46. */
  description?: string;
}

export interface CategoryListProps {
  categories: readonly CatalogCategory[];
  selected: string;
  onSelect?: (key: string) => void;
  /** The listbox's accessible name. */
  label?: string;
  className?: string;
}

/**
 * The Categories card (C-11 §3, C-14 §1): a 34 header band, then rows with a count pill; the
 * selected row is sel-bg and 500 with its pill white e1. A listbox with a roving tabindex: ↑ ↓
 * Home End move the selection and the focus together.
 */
export function CategoryList({
  categories,
  selected,
  onSelect,
  label = "Categories",
  className,
}: CategoryListProps): JSX.Element {
  const refs = useRef<(HTMLDivElement | null)[]>([]);
  const index = Math.max(
    0,
    categories.findIndex((c) => c.key === selected),
  );
  const move = (event: KeyboardEvent<HTMLDivElement>, i: number): void => {
    const n = categories.length;
    const to =
      event.key === "ArrowDown"
        ? Math.min(n - 1, i + 1)
        : event.key === "ArrowUp"
          ? Math.max(0, i - 1)
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? n - 1
              : null;
    if (to === null) return;
    event.preventDefault();
    const next = categories[to];
    if (next === undefined) return;
    onSelect?.(next.key);
    refs.current[to]?.focus();
  };
  return (
    <section
      data-catalog="categories"
      className={cn(
        "mx-[10px] mb-[10px] overflow-hidden rounded-pane bg-card inset-shadow-hair",
        className,
      )}
    >
      <h3 className="flex h-[34px] items-center bg-band-hd px-[12px] text-section hairline-b">
        {label}
      </h3>
      <div role="listbox" aria-label={label} className="flex flex-col">
        {categories.map((c, i) => {
          const on = c.key === selected;
          return (
            <div
              key={c.key}
              ref={(el) => {
                refs.current[i] = el;
              }}
              role="option"
              aria-selected={on}
              tabIndex={i === index ? 0 : -1}
              data-category={c.key}
              onClick={() => onSelect?.(c.key)}
              onKeyDown={(e) => {
                move(e, i);
              }}
              className={cn(
                "flex cursor-default items-center gap-[10px] pr-[8px] pl-[12px] text-body transition-colors duration-[200ms] not-first:hairline-t",
                c.description === undefined ? "h-[33px]" : "h-[46px]",
                on ? "bg-sel-bg font-medium" : "hover:bg-nav-fill",
              )}
            >
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate">{c.label}</span>
                {c.description !== undefined && (
                  <span className="truncate text-meta font-normal text-ink-3">
                    {c.description}
                  </span>
                )}
              </span>
              <span
                data-count=""
                className={cn(
                  "inline-flex h-[20px] min-w-[20px] flex-none items-center justify-center rounded-pill px-[6px] text-count font-medium text-ink-2",
                  on ? "bg-card shadow-e1" : "bg-chip",
                )}
              >
                {c.count}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
